"""Motor de despliegue: ejecuta una revisión paso a paso y se recupera si algo falla.

Se ejecuta SÍNCRONO en un hilo del worker (ver `main.py`); solo habla con el agente, nunca con
Docker. Hay TRES estados distintos, que no deben confundirse:

1. Estado lógico de la aplicación (`applications.status`): `draft` (nunca desplegada con éxito),
   `running` (debería estar funcionando), `stopped` (detenida por el administrador) y
   `attention` (requiere intervención).
2. Estado de la revisión (`deployments.status`): su ciclo de vida (ver repositories/deployments).
3. Estado REAL de los contenedores: se pregunta siempre al agente; no se deduce de SQLite.

Algoritmo de `run`: preparar (catálogo, imágenes, redes) -> parar la revisión anterior (sin
borrarla) -> crear y arrancar los servicios -> verificar su salud. Si todo va bien, la revisión
nueva pasa a `healthy` y se borra la anterior. Si algo falla (incluido un plazo agotado
con el agente: Docker pudo haber ejecutado la acción), se borran SOLO los contenedores de esta
operación y se vuelve a arrancar la revisión anterior.
"""

import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta

from minipaas.common.agent_protocol import ContainerInfo, CreateContainerRequest, ServiceSpec
from minipaas.common.catalog import CatalogError, get_entry
from minipaas.controlplane.agent_runtime_client import (
    AgentError,
    AgentRuntimeClient,
    AgentUnavailable,
)
from minipaas.controlplane.clock import Clock, to_iso
from minipaas.controlplane.db.connection import Database, transaction
from minipaas.controlplane.repositories import applications as apps_repo
from minipaas.controlplane.repositories import deployments as repo
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.repositories.deployments import Deployment, DeploymentService
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.errors import OPERATION_IN_PROGRESS, Conflict

logger = logging.getLogger(__name__)

NO_AGENT = "No se pudo contactar con el agente; revisa la aplicación y usa «Recuperar»"
LIVE_STATES = ("running", "restarting", "paused")  # contenedores que hay que parar
MAX_ERROR_LENGTH = 400


class DeployFailure(Exception):
    """Fallo esperado de una operación, con un mensaje no sensible apto para el administrador."""


class AppLocks:
    """Un cerrojo por aplicación: motor, parada, arranque, recuperación y borrado lo comparten."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def for_app(self, slug: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(slug, threading.Lock())

    @contextmanager
    def exclusive(self, slug: str) -> Iterator[None]:
        """Cerrojo SIN esperar: si otra operación lo tiene, se rechaza en vez de bloquear la
        petición HTTP hasta que termine (el motor puede tardar minutos)."""
        lock = self.for_app(slug)
        if not lock.acquire(blocking=False):
            raise Conflict(OPERATION_IN_PROGRESS)
        try:
            yield
        finally:
            lock.release()


def describe_error(error: Exception) -> tuple[str, bool]:
    """Mensaje no sensible de un error y si significa «agente inalcanzable»."""
    if isinstance(error, DeployFailure):
        return str(error), False
    if isinstance(error, AgentUnavailable):
        return NO_AGENT, True
    if isinstance(error, AgentError):
        return f"El agente no pudo completar la operación: {error}"[:MAX_ERROR_LENGTH], False
    logger.error("Error inesperado en una operación: %s", type(error).__name__)
    return "Error interno del control plane", False


class OperationAbandoned(Exception):
    """El control plane se está apagando: la operación se deja como está.

    No se marca como fallida ni se intenta un rollback, porque durante el apagado los clientes
    HTTP se cierran y cualquier error sería falso. Al volver a arrancar, la revisión sigue «en
    curso» y `interrupt_pending` la marca como interrumpida y recupera la aplicación (ADR-034).
    """


@dataclass
class Run:
    """Contexto de una ejecución: conexión propia del hilo y revisión que se despliega."""

    conn: sqlite3.Connection
    application: Application
    deployment: Deployment
    services: list[DeploymentService]
    previous: Deployment | None
    user_id: int | None
    client_ip: str | None


class DeployEngine:
    def __init__(
        self,
        db: Database,
        runtime: AgentRuntimeClient,
        audit_service: AuditService,
        locks: AppLocks,
        clock: Clock,
        include_test_catalog: bool,
        sleep: Callable[[float], None],
        stopping: threading.Event | None = None,
    ) -> None:
        self.db = db
        self.runtime = runtime
        self.audit = audit_service
        self.locks = locks
        self.clock = clock
        self.include_test = include_test_catalog
        self.sleep = sleep
        # Se activa al apagar el control plane: el motor deja de trabajar en la siguiente espera.
        self.stopping = stopping or threading.Event()

    def request_stop(self) -> None:
        self.stopping.set()

    def _check_stopping(self) -> None:
        if self.stopping.is_set():
            raise OperationAbandoned

    # --- Punto de entrada -----------------------------------------------------------------

    def run(self, slug: str, revision: int, user_id: int | None, client_ip: str | None) -> None:
        """Despliega una revisión que ya está en `preparing`. Nunca lanza."""
        with self.locks.for_app(slug):
            conn = self.db.connect()
            try:
                self._run(conn, slug, revision, user_id, client_ip)
            except Exception as error:  # el hilo del worker no debe morir en silencio
                logger.error("Fallo inesperado del motor: %s", type(error).__name__)
            finally:
                conn.close()

    def _run(self, conn, slug, revision, user_id, client_ip) -> None:
        application = apps_repo.get_by_slug(conn, slug)
        deployment = repo.get_by_revision(conn, application.id, revision) if application else None
        if deployment is None or deployment.status != "preparing":
            return  # nada que hacer: la revisión ya no está pendiente de ejecutar
        previous = None
        if deployment.previous_deployment_id is not None:
            previous = repo.get_by_id(conn, deployment.previous_deployment_id)
        services = repo.list_services(conn, deployment.id)
        run = Run(conn, application, deployment, services, previous, user_id, client_ip)
        self._audit(run, audit.DEPLOYMENT_START, audit.SUCCESS)
        try:
            self._prepare(run)
            self._replace_previous(run)
            self._create_and_start(run)
            self.verify(slug, deployment.operation_id, services)
            self._event(run, "verify", "success", "Todos los servicios responden correctamente")
        except Exception as error:
            if self.stopping.is_set():
                self._abandon(run)
                return
            message, unreachable = describe_error(error)
            self._on_failure(run, message, unreachable)
        else:
            self._on_success(run)

    def _abandon(self, run: Run) -> None:
        self._event(
            run,
            "result",
            "info",
            "El control plane se ha detenido durante la operación; se marcará como interrumpida",
        )

    # --- Pasos ----------------------------------------------------------------------------

    def _prepare(self, run: Run) -> None:
        slug = run.application.slug
        self._event(run, "prepare", "info", "Comprobando el catálogo del agente")
        agent_catalog = self.runtime.catalog()
        remote = {entry.id: entry for entry in agent_catalog.entries}
        for service in run.services:
            known = remote.get(service.catalog_id)
            try:
                local = get_entry(service.catalog_id, self.include_test)
            except CatalogError:
                local = None
            if (
                known is None
                or local is None
                or known.digest != local.digest
                or agent_catalog.architecture not in known.architectures
            ):
                raise DeployFailure("El agente no reconoce la imagen autorizada")
        for catalog_id in sorted({s.catalog_id for s in run.services}):
            result = self.runtime.ensure_image(catalog_id)
            action = "descargada" if result.pulled else "ya disponible"
            self._event(run, "prepare", "success", f"Imagen «{catalog_id}» {action}")
        self.runtime.ensure_networks(slug, run.application.id)
        self._event(run, "prepare", "success", "Redes de la aplicación preparadas")
        with transaction(run.conn):
            repo.set_status(run.conn, run.deployment.id, "deploying")

    def _replace_previous(self, run: Run) -> None:
        """Para (sin borrar) la revisión anterior: hace falta para poder recuperarla."""
        if run.previous is None:
            return
        slug = run.application.slug
        for container in self.containers_of(slug, run.previous.operation_id):
            if container.state in LIVE_STATES:
                self.runtime.stop_container(slug, container.name)
                self._event(
                    run, "deploy", "info", f"Servicio «{container.service_name}» anterior parado"
                )

    def _create_and_start(self, run: Run) -> None:
        slug = run.application.slug
        for service in run.services:
            spec = ServiceSpec(
                service_name=service.service_name,
                catalog_id=service.catalog_id,
                internal_port=service.internal_port,
                host_port=service.host_port,
                env=service.env,
                memory_mb=service.memory_mb,
                cpus=service.cpus,
            )
            request = CreateContainerRequest(
                operation_id=run.deployment.operation_id,
                app_id=run.application.id,
                app_slug=slug,
                revision=run.deployment.revision,
                service=spec,
            )
            container = self.runtime.create_container(slug, request)
            self.runtime.start_container(slug, container.name)
            self._event(run, "deploy", "success", f"Servicio «{service.service_name}» arrancado")

    def verify(self, slug: str, operation_id: str, services: list[DeploymentService]) -> None:
        """Espera hasta que todos los servicios estén en marcha y respondan a la sonda.

        Lanza DeployFailure si uno se detiene o si se agota el plazo del catálogo.
        """
        entries = [get_entry(s.catalog_id, self.include_test) for s in services]
        max_wait = max(e.health.max_wait_seconds for e in entries)
        interval = min(e.health.interval_seconds for e in entries)
        deadline = self.clock() + timedelta(seconds=max_wait)
        while True:
            self._check_stopping()
            waiting = self._unhealthy_services(slug, operation_id, services)
            if not waiting:
                return
            if self.clock() >= deadline:
                raise DeployFailure(
                    f"El servicio «{waiting[0]}» no respondió a la comprobación de salud en "
                    f"{max_wait} s"
                )
            self.sleep(interval)

    def _unhealthy_services(self, slug, operation_id, services) -> list[str]:
        """Nombres de los servicios que aún no están sanos; falla si alguno se ha detenido."""
        by_name = {c.service_name: c for c in self.containers_of(slug, operation_id)}
        waiting = []
        for service in services:
            container = by_name.get(service.service_name)
            if container is None:
                raise DeployFailure(f"El servicio «{service.service_name}» no existe en el agente")
            if container.state in ("exited", "dead"):
                raise DeployFailure(_stopped_message(service.service_name, container))
            if container.state != "running" or not self.runtime.probe(slug, container.name).healthy:
                waiting.append(service.service_name)
        return waiting

    def containers_of(self, slug: str, operation_id: str) -> list[ContainerInfo]:
        """Contenedores REALES de una operación, según el agente."""
        return [c for c in self.runtime.list_containers(slug) if c.operation_id == operation_id]

    # --- Éxito ----------------------------------------------------------------------------

    def _on_success(self, run: Run) -> None:
        now = to_iso(self.clock())
        with transaction(run.conn):
            repo.set_status(run.conn, run.deployment.id, "healthy", finished_at=now)
            if run.previous is not None:
                repo.set_status(run.conn, run.previous.id, "superseded")
            apps_repo.set_active_deployment(
                run.conn, run.application.id, run.deployment.id, "running", now
            )
            repo.add_event(
                run.conn, run.deployment.id, now, "result", "success", "Despliegue completado"
            )
            self._audit(run, audit.DEPLOYMENT_SUCCESS, audit.SUCCESS, in_transaction=True)
        if run.previous is not None:  # fuera de la transacción: es una operación de Docker
            self._remove_previous(run)

    def _remove_previous(self, run: Run) -> None:
        try:
            self.runtime.cleanup_operation(run.application.slug, run.previous.operation_id)
            self._event(run, "cleanup", "info", "Revisión anterior eliminada")
        except AgentError:
            self._event(
                run,
                "cleanup",
                "info",
                "No se pudo borrar la revisión anterior; «Recuperar» la limpiará",
            )

    # --- Fallo y recuperación -------------------------------------------------------------

    def _on_failure(self, run: Run, message: str, unreachable: bool) -> None:
        self._event(run, "result", "failure", message)
        self._audit(run, audit.DEPLOYMENT_FAILURE, audit.FAILURE, reason=message)
        if unreachable:
            self._audit(run, audit.AGENT_UNREACHABLE, audit.FAILURE)
        try:
            self._roll_back(run, message)
        except Exception as error:  # el propio cleanup o el rollback no pudieron completarse
            if self.stopping.is_set():
                self._abandon(run)
                return
            detail, unreachable = describe_error(error)
            if unreachable:
                self._audit(run, audit.AGENT_UNREACHABLE, audit.FAILURE)
            self._give_up(run, message, detail)

    def _roll_back(self, run: Run, reason: str) -> None:
        slug = run.application.slug
        self.runtime.cleanup_operation(slug, run.deployment.operation_id)  # SOLO esta operación
        self._event(run, "cleanup", "info", "Contenedores de esta revisión eliminados")
        if run.previous is None:
            self._finish(run, "failed", None, reason, "Despliegue fallido")
            self._remove_networks(run)
            return
        self._set_status(run, "rolling_back")
        self._audit(run, audit.DEPLOYMENT_ROLLBACK_START, audit.SUCCESS)
        if run.previous.status == "stopped":  # la anterior estaba detenida: no se arranca
            self._finish(
                run, "rolled_back", "stopped", reason, "Versión anterior recuperada (detenida)"
            )
            self._audit(run, audit.DEPLOYMENT_ROLLBACK_SUCCESS, audit.SUCCESS)
            return
        try:
            self._restart_previous(run)
        except AgentUnavailable:
            raise
        except (DeployFailure, AgentError) as error:
            detail, _ = describe_error(error)
            self._give_up(run, reason, detail)
            return
        self._finish(run, "rolled_back", "running", reason, "Versión anterior recuperada")
        self._audit(run, audit.DEPLOYMENT_ROLLBACK_SUCCESS, audit.SUCCESS)

    def _restart_previous(self, run: Run) -> None:
        slug, previous = run.application.slug, run.previous
        for container in self.containers_of(slug, previous.operation_id):
            if container.state != "running":
                self.runtime.start_container(slug, container.name)
        self.verify(slug, previous.operation_id, repo.list_services(run.conn, previous.id))

    def _remove_networks(self, run: Run) -> None:
        try:
            self.runtime.delete_networks(run.application.slug)
        except AgentError:
            self._event(run, "cleanup", "info", "No se pudieron borrar las redes de la aplicación")

    def _give_up(self, run: Run, reason: str, detail: str) -> None:
        """No se pudo limpiar o recuperar: la aplicación necesita intervención."""
        status = "rollback_failed" if run.previous else "failed"
        error = f"{reason}. {detail}"
        self._finish(run, status, "attention", error, detail)
        if run.previous:
            self._audit(run, audit.DEPLOYMENT_ROLLBACK_FAILURE, audit.FAILURE, reason=detail)

    # --- Escrituras en la base de datos ---------------------------------------------------

    def _set_status(self, run: Run, status: str) -> None:
        with transaction(run.conn):
            repo.set_status(run.conn, run.deployment.id, status)

    def _finish(
        self, run: Run, status: str, app_status: str | None, error: str, message: str
    ) -> None:
        """Estado final de la revisión (y de la aplicación, si cambia) en una transacción."""
        now = to_iso(self.clock())
        outcome = "failure" if status in ("failed", "rollback_failed") else "info"
        with transaction(run.conn):
            repo.set_status(
                run.conn, run.deployment.id, status, error=error[:MAX_ERROR_LENGTH], finished_at=now
            )
            if app_status is not None:
                apps_repo.set_status(run.conn, run.application.id, app_status, now)
            repo.add_event(run.conn, run.deployment.id, now, "result", outcome, message)

    def _event(self, run: Run, step: str, outcome: str, message: str) -> None:
        with transaction(run.conn):
            repo.add_event(
                run.conn, run.deployment.id, to_iso(self.clock()), step, outcome, message
            )

    def _audit(
        self,
        run: Run,
        event_type: str,
        outcome: str,
        reason: str | None = None,
        in_transaction: bool = False,
    ) -> None:
        """Evento de auditoría de una operación (solo revisión y operación, nunca valores)."""
        metadata = {"revision": run.deployment.revision, "operation": run.deployment.operation_id}
        if reason is not None:
            metadata["reason"] = reason[: audit.MAX_TEXT_LENGTH]
        details = {
            "user_id": run.user_id,
            "resource_type": "application",
            "resource_id": run.application.slug,
            "client_ip": run.client_ip,
            "metadata": metadata,
        }
        if in_transaction:  # el éxito se escribe en la misma transacción que el cambio de estado
            self.audit.record(run.conn, event_type, outcome, **details)
        else:
            with transaction(run.conn):
                self.audit.record(run.conn, event_type, outcome, **details)


def _stopped_message(name: str, container: ContainerInfo) -> str:
    message = f"El servicio «{name}» se detuvo al arrancar (código {container.exit_code})"
    if container.oom_killed:
        message += " por falta de memoria"
    return message
