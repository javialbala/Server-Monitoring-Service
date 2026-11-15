"""Ciclo de vida de una aplicación ya desplegada: parar, arrancar, recuperar, borrar y consultar.

Todas las operaciones toman el cerrojo de la aplicación (el mismo que el motor de despliegue),
así que nunca se mezclan dos operaciones sobre los mismos contenedores. El estado REAL de los
contenedores se pregunta siempre al agente; en la base de datos solo se guarda el estado lógico.
"""

import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from minipaas.common.agent_protocol import ContainerInfo
from minipaas.controlplane.agent_runtime_client import (
    AgentError,
    AgentRejected,
    AgentRuntimeClient,
    AgentUnavailable,
)
from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.db.connection import Database, transaction
from minipaas.controlplane.repositories import applications as apps_repo
from minipaas.controlplane.repositories import deployments as repo
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.applications import ApplicationService
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.deploy_engine import (
    LIVE_STATES,
    AppLocks,
    DeployEngine,
    DeployFailure,
    describe_error,
)
from minipaas.controlplane.services.deployments import get_application
from minipaas.controlplane.services.errors import (
    OPERATION_IN_PROGRESS,
    AgentDown,
    BadGateway,
    Conflict,
    ServiceError,
)

logger = logging.getLogger(__name__)

# Revisiones cuyos contenedores sobrantes se borran al recuperar la aplicación.
CLEANABLE = ("failed", "rolled_back", "rollback_failed", "interrupted", "superseded", "discarded")
INTERRUPTED_MESSAGE = "Operación interrumpida por un reinicio del control plane"
STATE_LABELS = {
    "running": "En ejecución",
    "exited": "Detenido",
    "created": "Creado",
    "restarting": "Reiniciando",
    "paused": "En pausa",
    "dead": "Con error",
    "removing": "Eliminando",
}


@dataclass(frozen=True)
class RuntimeService:
    container: ContainerInfo
    state_label: str
    access_url: str | None


@dataclass(frozen=True)
class RuntimeView:
    agent_reachable: bool
    active_revision: int | None
    services: list[RuntimeService]
    unknown_containers: int


class AppLifecycle:
    def __init__(
        self,
        db: Database,
        runtime: AgentRuntimeClient,
        engine: DeployEngine,
        applications: ApplicationService,
        audit_service: AuditService,
        locks: AppLocks,
        enqueue_recover: Callable[[str], None],
        clock: Clock = utc_now,
    ) -> None:
        self.db = db
        self.runtime = runtime
        self.engine = engine
        self.applications = applications
        self.audit = audit_service
        self.locks = locks
        self.enqueue_recover = enqueue_recover
        self.clock = clock

    # --- Consulta del estado real ---------------------------------------------------------

    def runtime_view(self, conn: sqlite3.Connection, slug: str) -> RuntimeView:
        """Contenedores reales de la revisión activa. Con el agente caído no falla."""
        application = get_application(conn, slug)
        try:
            containers = self.runtime.list_containers(slug)
        except AgentError:
            return RuntimeView(False, application.active_revision, [], 0)
        known = {d.operation_id for d in repo.list_for_app(conn, application.id)}
        unknown = sum(1 for c in containers if c.operation_id not in known)
        active = self._active(conn, application)
        shown = [c for c in containers if active and c.operation_id == active.operation_id]
        services = [RuntimeService(c, STATE_LABELS[c.state], _access_url(c)) for c in shown]
        return RuntimeView(True, application.active_revision, services, unknown)

    # --- Parar y arrancar -----------------------------------------------------------------

    def stop(
        self, conn: sqlite3.Connection, slug: str, user_id: int, client_ip: str
    ) -> Application:
        with self.locks.exclusive(slug):
            application = self._require(
                conn, slug, "running", "La aplicación no está en funcionamiento"
            )
            active = self._active(conn, application)
            with self._agent_errors(conn, audit.APPLICATION_STOP, slug, user_id, client_ip):
                self._stop_live(slug, active.operation_id)
            with transaction(conn):
                now = to_iso(self.clock())
                repo.set_status(conn, active.id, "stopped")
                apps_repo.set_status(conn, application.id, "stopped", now)
                self._record(conn, audit.APPLICATION_STOP, audit.SUCCESS, slug, user_id, client_ip)
        return apps_repo.get_by_slug(conn, slug)

    def start(
        self, conn: sqlite3.Connection, slug: str, user_id: int, client_ip: str
    ) -> Application:
        with self.locks.exclusive(slug):
            application = self._require(conn, slug, "stopped", "La aplicación no está detenida")
            active = self._active(conn, application)
            try:
                self._start_and_verify(conn, slug, active)
            except Exception as error:
                message, unreachable = describe_error(error)
                self._start_failed(conn, application, message, unreachable, user_id, client_ip)
            with transaction(conn):
                repo.set_status(conn, active.id, "healthy")
                apps_repo.set_status(conn, application.id, "running", to_iso(self.clock()))
                self._record(conn, audit.APPLICATION_START, audit.SUCCESS, slug, user_id, client_ip)
        return apps_repo.get_by_slug(conn, slug)

    def _start_failed(self, conn, application, message, unreachable, user_id, client_ip) -> None:
        with transaction(conn):
            apps_repo.set_status(conn, application.id, "attention", to_iso(self.clock()))
        slug = application.slug
        self._record_failure(conn, audit.APPLICATION_START, slug, user_id, client_ip, message)
        if unreachable:
            self._record_failure(conn, audit.AGENT_UNREACHABLE, slug, user_id, client_ip, message)
            raise AgentDown()
        raise BadGateway(f"No se pudo arrancar: {message}")

    def _start_and_verify(self, conn: sqlite3.Connection, slug: str, active) -> None:
        for container in self.engine.containers_of(slug, active.operation_id):
            if container.state != "running":
                self.runtime.start_container(slug, container.name)
        self.engine.verify(slug, active.operation_id, repo.list_services(conn, active.id))

    # --- Recuperar ------------------------------------------------------------------------

    def recover(
        self, conn: sqlite3.Connection, slug: str, user_id: int | None, client_ip: str | None
    ) -> Application:
        """Limpia lo que sobra, no toca lo desconocido y devuelve la aplicación a un estado
        coherente con su revisión activa (si falla algo, `attention`)."""
        with self.locks.exclusive(slug):
            application = get_application(conn, slug)
            if application.operation_in_progress:
                raise Conflict(OPERATION_IN_PROGRESS)
            with self._agent_errors(conn, audit.APPLICATION_RECOVER, slug, user_id, client_ip):
                status, problem = self._recover(conn, application)
            with transaction(conn):
                apps_repo.set_status(conn, application.id, status, to_iso(self.clock()))
                outcome = audit.FAILURE if status == "attention" else audit.SUCCESS
                self._record(
                    conn, audit.APPLICATION_RECOVER, outcome, slug, user_id, client_ip, problem
                )
        return apps_repo.get_by_slug(conn, slug)

    def _recover(
        self, conn: sqlite3.Connection, application: Application
    ) -> tuple[str, str | None]:
        """Devuelve el estado lógico resultante y, si es `attention`, el motivo."""
        slug = application.slug
        by_operation = {d.operation_id: d for d in repo.list_for_app(conn, application.id)}
        containers = self.runtime.list_containers(slug)
        for operation_id in sorted({c.operation_id for c in containers}):
            known = by_operation.get(operation_id)
            if known is not None and known.status in CLEANABLE:
                self.runtime.cleanup_operation(slug, operation_id)
        unknown = sum(1 for c in containers if c.operation_id not in by_operation)
        status, problem = self._restore_active(conn, application)
        if unknown:  # nunca se tocan: se informa al administrador
            return "attention", f"Hay {unknown} contenedor(es) de una operación desconocida"
        return status, problem

    def _restore_active(self, conn, application: Application) -> tuple[str, str | None]:
        slug = application.slug
        active = self._active(conn, application)
        if active is None:  # nunca se desplegó con éxito: no debe quedar nada
            try:
                self.runtime.delete_networks(slug)
            except AgentRejected:
                pass  # quedan contenedores que no son nuestros: se informan aparte
            return "draft", None
        if active.status == "stopped":
            self._stop_live(slug, active.operation_id)
            return "stopped", None
        try:
            self._start_and_verify(conn, slug, active)
        except DeployFailure as error:
            return "attention", str(error)
        return "running", None

    def recover_quietly(self, slug: str) -> None:
        """Recuperación automática al arrancar: si el agente no responde, queda `attention`."""
        conn = self.db.connect()
        try:
            self.recover(conn, slug, None, None)
        except ServiceError as error:
            logger.warning("Recuperación automática de %s sin completar: %s", slug, error.reason)
        except Exception as error:
            logger.error("Fallo inesperado al recuperar %s: %s", slug, type(error).__name__)
        finally:
            conn.close()

    def interrupt_pending(self) -> None:
        """Al arrancar: las operaciones que quedaron a medias pasan a `interrupted`."""
        conn = self.db.connect()
        try:
            slugs = [self._interrupt(conn, d) for d in repo.list_in_progress(conn)]
        finally:
            conn.close()
        for slug in slugs:
            self.enqueue_recover(slug)

    def _interrupt(self, conn: sqlite3.Connection, deployment) -> str:
        application = apps_repo.get_by_id(conn, deployment.application_id)
        now = to_iso(self.clock())
        with transaction(conn):
            repo.set_status(
                conn, deployment.id, "interrupted", error=INTERRUPTED_MESSAGE, finished_at=now
            )
            repo.add_event(conn, deployment.id, now, "result", "failure", INTERRUPTED_MESSAGE)
            apps_repo.set_status(conn, application.id, "attention", now)
            self.audit.record(
                conn,
                audit.DEPLOYMENT_INTERRUPTED,
                audit.FAILURE,
                resource_type="application",
                resource_id=application.slug,
                metadata={"revision": deployment.revision, "operation": deployment.operation_id},
            )
        return application.slug

    # --- Borrar ---------------------------------------------------------------------------

    def delete_application(
        self, conn: sqlite3.Connection, slug: str, user_id: int, client_ip: str
    ) -> None:
        """Borra la aplicación. Si tuvo revisiones, antes el agente elimina contenedores y redes
        y, solo si responde bien, se borra de la base de datos."""
        with self.locks.exclusive(slug):
            application = apps_repo.get_by_slug(conn, slug)
            if application is not None:
                if application.operation_in_progress:
                    raise Conflict(OPERATION_IN_PROGRESS)
                if repo.list_for_app(conn, application.id):
                    message = (
                        "No se puede contactar con el agente; no se elimina para no dejar "
                        "recursos sin control"
                    )
                    with self._agent_errors(
                        conn, audit.APPLICATION_DELETE, slug, user_id, client_ip, message
                    ):
                        self.runtime.delete_app(slug)
            self.applications.delete(conn, slug, user_id, client_ip)  # 404 si no existe

    # --- Interno --------------------------------------------------------------------------

    def _require(self, conn, slug: str, status: str, message: str) -> Application:
        application = get_application(conn, slug)
        if application.operation_in_progress:
            raise Conflict(OPERATION_IN_PROGRESS)
        if application.status != status:
            raise Conflict(message)
        return application

    @staticmethod
    def _active(conn: sqlite3.Connection, application: Application):
        if application.active_deployment_id is None:
            return None
        return repo.get_by_id(conn, application.active_deployment_id)

    def _stop_live(self, slug: str, operation_id: str) -> None:
        for container in self.engine.containers_of(slug, operation_id):
            if container.state in LIVE_STATES:
                self.runtime.stop_container(slug, container.name)

    @contextmanager
    def _agent_errors(
        self, conn, event_type: str, slug: str, user_id, client_ip, down_message: str | None = None
    ) -> Iterator[None]:
        """Convierte los errores del agente en errores de dominio y audita el fallo."""
        try:
            yield
        except AgentError as error:
            if isinstance(error, AgentUnavailable):
                converted = AgentDown(down_message or "No se puede contactar con el agente")
            else:
                converted = BadGateway("El agente no pudo completar la operación")
            self._record_failure(conn, event_type, slug, user_id, client_ip, converted.reason)
            if isinstance(error, AgentUnavailable):
                self._record_failure(
                    conn, audit.AGENT_UNREACHABLE, slug, user_id, client_ip, converted.reason
                )
            raise converted from None

    def _record(self, conn, event_type, outcome, slug, user_id, client_ip, reason=None) -> None:
        self.audit.record(
            conn,
            event_type,
            outcome,
            user_id=user_id,
            resource_type="application",
            resource_id=slug,
            client_ip=client_ip,
            metadata={"reason": reason[:200]} if reason else None,
        )

    def _record_failure(self, conn, event_type, slug, user_id, client_ip, reason: str) -> None:
        self.audit.record_failure(
            conn,
            event_type,
            reason[:200],
            user_id=user_id,
            resource_type="application",
            resource_id=slug,
            client_ip=client_ip,
        )


def _access_url(container: ContainerInfo) -> str | None:
    if container.state != "running" or container.host_port is None or not container.publish_address:
        return None
    return f"http://{container.publish_address}:{container.host_port}/"
