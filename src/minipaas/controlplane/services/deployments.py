"""Casos de uso de revisiones: crear, solicitar el despliegue y consultar el historial.

Crear una revisión y solicitar su despliegue son dos pasos: el primero congela la configuración
de los servicios (copia inmutable); el segundo la pasa a `preparing` y la encola en el worker.
Ambos son idempotentes ante peticiones repetidas del cliente.
"""

import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from minipaas.common.catalog import CatalogError, get_entry
from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.db.connection import transaction
from minipaas.controlplane.repositories import applications as apps_repo
from minipaas.controlplane.repositories import deployments as repo
from minipaas.controlplane.repositories import services as services_repo
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.repositories.deployments import (
    Deployment,
    DeploymentEvent,
    DeploymentService,
)
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.errors import (
    OPERATION_IN_PROGRESS,
    Conflict,
    NotFound,
    ServiceError,
)


@dataclass(frozen=True)
class DeploymentView:
    deployment: Deployment
    services: list[DeploymentService]
    events: list[DeploymentEvent] = field(default_factory=list)


def get_application(conn: sqlite3.Connection, slug: str) -> Application:
    application = apps_repo.get_by_slug(conn, slug)
    if application is None:
        raise NotFound("Aplicación no encontrada")
    return application


class Deployments:
    def __init__(
        self,
        audit_service: AuditService,
        include_test_catalog: bool,
        enqueue: Callable[[str, int, int, str], None],
        clock: Clock = utc_now,
    ) -> None:
        self.audit = audit_service
        self.include_test = include_test_catalog
        self.enqueue = enqueue  # (slug, revision, user_id, client_ip): encola el motor en el worker
        self.clock = clock

    # --- Consultas ------------------------------------------------------------------------

    def list(self, conn: sqlite3.Connection, slug: str) -> list[DeploymentView]:
        application = get_application(conn, slug)
        return [self._view(conn, d) for d in repo.list_for_app(conn, application.id)]

    def get(self, conn: sqlite3.Connection, slug: str, revision: int) -> DeploymentView:
        application = get_application(conn, slug)
        deployment = repo.get_by_revision(conn, application.id, revision)
        if deployment is None:
            raise NotFound("Revisión no encontrada")
        return self._view(conn, deployment, with_events=True)

    # --- Crear revisión -------------------------------------------------------------------

    def create_revision(
        self, conn: sqlite3.Connection, slug: str, request_id: str, user_id: int, client_ip: str
    ) -> tuple[DeploymentView, bool]:
        """Devuelve la revisión y si es nueva (False: ya existía con ese `request_id`)."""
        try:
            with transaction(conn):
                application = get_application(conn, slug)
                existing = repo.get_by_request_id(conn, application.id, request_id)
                if existing is not None:
                    return self._view(conn, existing), False
                deployment_id = self._insert_revision(conn, application, request_id)
                deployment = repo.get_by_id(conn, deployment_id)
                self.audit.record(
                    conn,
                    audit.DEPLOYMENT_REVISION_CREATE,
                    audit.SUCCESS,
                    user_id=user_id,
                    resource_type="application",
                    resource_id=slug,
                    client_ip=client_ip,
                    metadata={
                        "revision": deployment.revision,
                        "operation": deployment.operation_id,
                    },
                )
        except ServiceError as error:
            self._record_failure(
                audit.DEPLOYMENT_REVISION_CREATE, conn, slug, user_id, client_ip, error
            )
            raise
        return self._view(conn, deployment), True

    def _insert_revision(
        self, conn: sqlite3.Connection, application: Application, request_id: str
    ) -> int:
        services = services_repo.list_for_app(conn, application.id)
        if not services:
            raise Conflict("Añade al menos un servicio antes de desplegar")
        now = to_iso(self.clock())
        revision = repo.next_revision(conn, application.id)
        deployment_id = repo.insert_pending(
            conn, application.id, revision, str(uuid.uuid4()), request_id, now
        )
        for service in services:
            try:
                image_ref = get_entry(service.catalog_id, self.include_test).image_ref
            except CatalogError as error:
                raise Conflict(f"El servicio «{service.name}»: {error}") from None
            repo.insert_service(
                conn,
                deployment_id,
                DeploymentService(
                    service_name=service.name,
                    catalog_id=service.catalog_id,
                    image_ref=image_ref,
                    internal_port=service.internal_port,
                    host_port=service.host_port,
                    env=service.env,
                    memory_mb=service.memory_mb,
                    cpus=service.cpus,
                ),
            )
        repo.discard_pending(conn, application.id, deployment_id, now)
        return deployment_id

    # --- Solicitar el despliegue ----------------------------------------------------------

    def request_deploy(
        self, conn: sqlite3.Connection, slug: str, revision: int, user_id: int, client_ip: str
    ) -> tuple[DeploymentView, bool]:
        """Pasa la revisión a `preparing` y la encola. Devuelve (revisión, aceptada).

        Si la revisión ya no está `pending` no hace nada y devuelve su estado actual
        (idempotente). Si hay otra operación en curso en la aplicación, la base de datos lo impide
        (índice único `one_operation_per_app`) y se responde con un conflicto.
        """
        try:
            with transaction(conn):
                application = get_application(conn, slug)
                deployment = repo.get_by_revision(conn, application.id, revision)
                if deployment is None:
                    raise NotFound("Revisión no encontrada")
                if deployment.status != "pending" or not self._mark_preparing(
                    conn, application, deployment
                ):
                    return self._view(conn, deployment), False
                self.audit.record(
                    conn,
                    audit.DEPLOYMENT_REQUEST,
                    audit.SUCCESS,
                    user_id=user_id,
                    resource_type="application",
                    resource_id=slug,
                    client_ip=client_ip,
                    metadata={"revision": revision, "operation": deployment.operation_id},
                )
        except ServiceError as error:
            self._record_failure(audit.DEPLOYMENT_REQUEST, conn, slug, user_id, client_ip, error)
            raise
        self.enqueue(slug, revision, user_id, client_ip)
        return self._view(conn, repo.get_by_id(conn, deployment.id)), True

    def _mark_preparing(
        self, conn: sqlite3.Connection, application: Application, deployment: Deployment
    ) -> bool:
        try:
            return repo.mark_preparing(
                conn, deployment.id, application.active_deployment_id, to_iso(self.clock())
            )
        except sqlite3.IntegrityError as error:
            if "deployments.application_id" in str(error):
                raise Conflict(OPERATION_IN_PROGRESS) from None
            raise

    # --- Interno --------------------------------------------------------------------------

    @staticmethod
    def _view(
        conn: sqlite3.Connection, deployment: Deployment, with_events: bool = False
    ) -> DeploymentView:
        events = repo.list_events(conn, deployment.id) if with_events else []
        return DeploymentView(deployment, repo.list_services(conn, deployment.id), events)

    def _record_failure(self, event_type, conn, slug, user_id, client_ip, error) -> None:
        self.audit.record_failure(
            conn,
            event_type,
            error.reason,
            user_id=user_id,
            resource_type="application",
            resource_id=slug,
            client_ip=client_ip,
        )
