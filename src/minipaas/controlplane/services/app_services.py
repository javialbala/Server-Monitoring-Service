"""Casos de uso de los servicios de una aplicación (configuración editable, no la desplegada).

Toda configuración se valida con el catálogo cerrado (`validate_service_config`). La comprobación
de la arquitectura la hace el agente, que es quien conoce el host. Los valores de `env` no se
escriben en la auditoría ni en los logs: solo los nombres de los campos modificados.
"""

import sqlite3
from dataclasses import dataclass

from minipaas.common.catalog import (
    HOST_PORT_MAX,
    HOST_PORT_MIN,
    CatalogError,
    ServiceConfig,
    get_entry,
    validate_service_config,
)
from minipaas.common.naming import is_valid_service_name
from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.db.connection import transaction
from minipaas.controlplane.repositories import applications as apps_repo
from minipaas.controlplane.repositories import deployments as deployments_repo
from minipaas.controlplane.repositories import services as repo
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.repositories.services import Service
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.errors import Conflict, Invalid, NotFound, ServiceError

PROTECTED_MESSAGE = (
    "El servicio forma parte del despliegue en funcionamiento. "
    "Detén la aplicación o despliega una revisión sin él."
)
NAME_HELP = (
    "El nombre del servicio debe tener entre 2 y 30 caracteres, empezar por una letra minúscula, "
    "terminar en letra o número y contener solo minúsculas, números y guiones simples."
)


@dataclass(frozen=True)
class ServiceView:
    service: Service
    catalog_name: str
    protected: bool  # forma parte de la revisión en funcionamiento: no se puede borrar


@dataclass(frozen=True)
class ServiceChanges:
    """Cambios pedidos por PATCH. Un campo `None` (o ausente) significa «no tocar»."""

    internal_port: int | None = None
    publish: bool | None = None
    host_port: int | None = None
    env: dict[str, str] | None = None
    memory_mb: int | None = None
    cpus: float | None = None


def _validate(
    include_test: bool, catalog_id: str, host_port: int | None, **values
) -> ServiceConfig:
    try:
        entry = get_entry(catalog_id, include_test)
        return validate_service_config(entry, host_port=host_port, **values)
    except CatalogError as error:
        raise Invalid(str(error)) from None


class AppServices:
    def __init__(
        self, audit_service: AuditService, include_test_catalog: bool, clock: Clock = utc_now
    ) -> None:
        self.audit = audit_service
        self.include_test = include_test_catalog
        self.clock = clock

    # --- Consultas ------------------------------------------------------------------------

    def list_services(self, conn: sqlite3.Connection, slug: str) -> list[ServiceView]:
        application = self._application(conn, slug)
        return [self._view(conn, application, s) for s in repo.list_for_app(conn, application.id)]

    def get(self, conn: sqlite3.Connection, slug: str, name: str) -> ServiceView:
        application = self._application(conn, slug)
        return self._view(conn, application, self._service(conn, application, name))

    # --- Altas, cambios y bajas -----------------------------------------------------------

    def create(
        self,
        conn: sqlite3.Connection,
        slug: str,
        *,
        name: str,
        catalog_id: str,
        publish: bool,
        host_port: int | None,
        user_id: int,
        client_ip: str,
        **values,
    ) -> ServiceView:
        resource = f"{slug}/{name}"
        try:
            if not is_valid_service_name(name):
                raise Invalid(NAME_HELP)
            config = _validate(
                self.include_test, catalog_id, host_port if publish else None, **values
            )
            with transaction(conn):
                application = self._application(conn, slug)
                port = self._choose_port(conn, application.id, None, publish, host_port)
                if port != config.host_port:  # puerto asignado automáticamente: se valida otra vez
                    config = _validate(self.include_test, catalog_id, port, **values)
                self._insert(conn, application, name, config)
                self._record(conn, audit.SERVICE_CREATE, resource, user_id, client_ip)
        except ServiceError as error:
            self._record_failure(audit.SERVICE_CREATE, conn, resource, user_id, client_ip, error)
            raise
        return self.get(conn, slug, name)

    def update(
        self,
        conn: sqlite3.Connection,
        slug: str,
        name: str,
        changes: ServiceChanges,
        user_id: int,
        client_ip: str,
    ) -> ServiceView:
        resource = f"{slug}/{name}"
        try:
            with transaction(conn):
                application = self._application(conn, slug)
                current = self._service(conn, application, name)
                changed = self._apply_changes(conn, application, current, changes)
                if changed:
                    self._record(
                        conn,
                        audit.SERVICE_UPDATE,
                        resource,
                        user_id,
                        client_ip,
                        {"fields": ",".join(changed)},
                    )
        except ServiceError as error:
            self._record_failure(audit.SERVICE_UPDATE, conn, resource, user_id, client_ip, error)
            raise
        return self.get(conn, slug, name)

    def delete(
        self, conn: sqlite3.Connection, slug: str, name: str, user_id: int, client_ip: str
    ) -> None:
        resource = f"{slug}/{name}"
        try:
            with transaction(conn):
                application = self._application(conn, slug)
                service = self._service(conn, application, name)
                if self._view(conn, application, service).protected:
                    raise Conflict(PROTECTED_MESSAGE)
                repo.delete(conn, service.id)
                self._record(conn, audit.SERVICE_DELETE, resource, user_id, client_ip)
        except ServiceError as error:
            self._record_failure(audit.SERVICE_DELETE, conn, resource, user_id, client_ip, error)
            raise

    # --- Interno --------------------------------------------------------------------------

    def _apply_changes(
        self,
        conn: sqlite3.Connection,
        application: Application,
        current: Service,
        changes: ServiceChanges,
    ) -> list[str]:
        """Valida el resultado de aplicar los cambios, lo guarda y devuelve los campos tocados."""
        publish = changes.publish if changes.publish is not None else current.host_port is not None
        requested = changes.host_port if changes.host_port is not None else current.host_port
        port = self._choose_port(conn, application.id, current.id, publish, requested)
        env = changes.env if changes.env is not None else current.env
        values = {
            "internal_port": changes.internal_port or current.internal_port,
            "env": env,
            "memory_mb": changes.memory_mb or current.memory_mb,
            "cpus": changes.cpus or current.cpus,
        }
        config = _validate(self.include_test, current.catalog_id, port, **values)
        before = (current.internal_port, current.host_port, current.env, current.memory_mb)
        after = (config.internal_port, config.host_port, config.env_dict(), config.memory_mb)
        names = ("internal_port", "host_port", "env", "memory_mb")
        changed = [n for n, old, new in zip(names, before, after, strict=True) if old != new]
        if current.cpus != config.cpus:
            changed.append("cpus")
        if changed:
            repo.update(
                conn,
                current.id,
                config.internal_port,
                config.host_port,
                config.env_dict(),
                config.memory_mb,
                config.cpus,
                to_iso(self.clock()),
            )
        return changed

    def _choose_port(
        self,
        conn: sqlite3.Connection,
        app_id: int,
        own_id: int | None,
        publish: bool,
        requested: int | None,
    ) -> int | None:
        """Puerto del host: ninguno, el pedido (si está libre) o el menor libre del rango."""
        if not publish:
            return None
        reserved = repo.reserved_ports(conn, app_id, own_id)
        if requested is not None:
            if requested in reserved:
                raise Conflict(f"El puerto {requested} ya está asignado a otro servicio")
            return requested
        free = repo.first_free_port(reserved)
        if free is None:
            raise Conflict(f"No quedan puertos libres en el rango {HOST_PORT_MIN}–{HOST_PORT_MAX}")
        return free

    def _insert(
        self, conn: sqlite3.Connection, application: Application, name: str, config: ServiceConfig
    ) -> None:
        try:
            repo.insert(
                conn,
                application.id,
                name,
                config.catalog_id,
                config.internal_port,
                config.host_port,
                config.env_dict(),
                config.memory_mb,
                config.cpus,
                to_iso(self.clock()),
            )
        except sqlite3.IntegrityError as error:
            if "services.application_id" in str(error):
                raise Conflict("Ya existe un servicio con ese nombre en la aplicación") from None
            raise

    def _view(self, conn: sqlite3.Connection, application: Application, s: Service) -> ServiceView:
        try:
            catalog_name = get_entry(s.catalog_id, self.include_test).name
        except CatalogError:
            catalog_name = s.catalog_id  # entrada de prueba deshabilitada después de crearlo
        return ServiceView(s, catalog_name, self._is_protected(conn, application, s.name))

    @staticmethod
    def _is_protected(conn: sqlite3.Connection, application: Application, name: str) -> bool:
        if application.status != "running" or application.active_deployment_id is None:
            return False
        active = deployments_repo.list_services(conn, application.active_deployment_id)
        return any(s.service_name == name for s in active)

    @staticmethod
    def _application(conn: sqlite3.Connection, slug: str) -> Application:
        application = apps_repo.get_by_slug(conn, slug)
        if application is None:
            raise NotFound("Aplicación no encontrada")
        return application

    @staticmethod
    def _service(conn: sqlite3.Connection, application: Application, name: str) -> Service:
        service = repo.get(conn, application.id, name)
        if service is None:
            raise NotFound("Servicio no encontrado")
        return service

    def _record(self, conn, event_type, resource, user_id, client_ip, metadata=None) -> None:
        self.audit.record(
            conn,
            event_type,
            audit.SUCCESS,
            user_id=user_id,
            resource_type="service",
            resource_id=resource,
            client_ip=client_ip,
            metadata=metadata,
        )

    def _record_failure(self, event_type, conn, resource, user_id, client_ip, error) -> None:
        self.audit.record_failure(
            conn,
            event_type,
            error.reason,
            user_id=user_id,
            resource_type="service",
            resource_id=resource,
            client_ip=client_ip,
        )
