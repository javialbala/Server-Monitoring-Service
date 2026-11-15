"""Casos de uso de aplicaciones: alta, consulta, modificación y borrado."""

import re
import sqlite3
import unicodedata

from minipaas.controlplane.clock import Clock, to_iso, utc_now
from minipaas.controlplane.db.connection import transaction
from minipaas.controlplane.repositories import applications as repo
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService

# En la Fase 3 el slug será la base de nombres DNS y de Docker (contenedores, redes,
# volúmenes), así que se restringe ya: empieza por letra, termina en letra o dígito, solo
# minúsculas, dígitos y guiones, sin guiones dobles, entre 3 y 40 caracteres.
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")
SLUG_MAX_LENGTH = 40
SLUG_HELP = (
    "El identificador debe tener entre 3 y 40 caracteres, empezar por una letra minúscula, "
    "terminar en letra o número y contener solo minúsculas, números y guiones simples."
)


class InvalidSlug(ValueError):
    pass


class SlugAlreadyExists(Exception):
    pass


class ApplicationNotFound(Exception):
    pass


def validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.match(slug) or "--" in slug:
        raise InvalidSlug(SLUG_HELP)
    return slug


def slugify(name: str) -> str:
    """Deriva un slug del nombre: sin acentos, minúsculas y guiones en lugar de símbolos."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:SLUG_MAX_LENGTH].strip("-")


class ApplicationService:
    def __init__(self, audit_service: AuditService, clock: Clock = utc_now) -> None:
        self.audit = audit_service
        self.clock = clock

    def list(self, conn: sqlite3.Connection) -> list[Application]:
        return repo.list_all(conn)

    def get(self, conn: sqlite3.Connection, slug: str) -> Application:
        application = repo.get_by_slug(conn, slug)
        if application is None:
            raise ApplicationNotFound
        return application

    def create(
        self,
        conn: sqlite3.Connection,
        name: str,
        slug: str | None,
        description: str,
        user_id: int,
        client_ip: str,
    ) -> Application:
        slug = validate_slug(slug if slug is not None else slugify(name))
        try:
            with transaction(conn):
                # La unicidad la garantiza la restricción UNIQUE de la base de datos.
                try:
                    application = repo.create(conn, slug, name, description, to_iso(self.clock()))
                except sqlite3.IntegrityError as error:
                    if "UNIQUE" not in str(error):
                        raise  # otra restricción (CHECK...): es un fallo, no un duplicado
                    raise SlugAlreadyExists from None
                self._record_success(conn, audit.APPLICATION_CREATE, slug, user_id, client_ip)
        except SlugAlreadyExists:
            self._record_failure(
                conn, audit.APPLICATION_CREATE, slug, user_id, client_ip, "slug_exists"
            )
            raise
        return application

    def update(
        self,
        conn: sqlite3.Connection,
        slug: str,
        name: str | None,
        description: str | None,
        user_id: int,
        client_ip: str,
    ) -> Application:
        """Modifica nombre y/o descripción. El slug es INMUTABLE: será el nombre de los
        recursos Docker de la Fase 3 y cambiarlo dejaría recursos huérfanos."""
        try:
            with transaction(conn):
                current = self.get(conn, slug)
                new_name = current.name if name is None else name
                new_description = current.description if description is None else description
                changed = [
                    field
                    for field, old, new in (
                        ("name", current.name, new_name),
                        ("description", current.description, new_description),
                    )
                    if old != new
                ]
                if not changed:
                    return current  # sin cambios: ni escritura ni evento de auditoría
                application = repo.update(
                    conn, slug, new_name, new_description, to_iso(self.clock())
                )
                self._record_success(
                    conn,
                    audit.APPLICATION_UPDATE,
                    slug,
                    user_id,
                    client_ip,
                    {"fields": ",".join(changed)},
                )
        except ApplicationNotFound:
            self._record_failure(
                conn, audit.APPLICATION_UPDATE, slug, user_id, client_ip, "not_found"
            )
            raise
        return application

    def delete(self, conn: sqlite3.Connection, slug: str, user_id: int, client_ip: str) -> None:
        """Borrado definitivo. En esta fase una aplicación no tiene recursos Docker que
        limpiar; la Fase 3 revisará este flujo. El evento de auditoría conserva el rastro."""
        try:
            with transaction(conn):
                if not repo.delete(conn, slug):
                    raise ApplicationNotFound
                self._record_success(conn, audit.APPLICATION_DELETE, slug, user_id, client_ip)
        except ApplicationNotFound:
            self._record_failure(
                conn, audit.APPLICATION_DELETE, slug, user_id, client_ip, "not_found"
            )
            raise

    def _record_success(
        self, conn, event_type, slug, user_id, client_ip, metadata: dict | None = None
    ) -> None:
        self.audit.record(
            conn,
            event_type,
            audit.SUCCESS,
            user_id=user_id,
            resource_type="application",
            resource_id=slug,
            client_ip=client_ip,
            metadata=metadata,
        )

    def _record_failure(self, conn, event_type, slug, user_id, client_ip, reason: str) -> None:
        with transaction(conn):
            self.audit.record(
                conn,
                event_type,
                audit.FAILURE,
                user_id=user_id,
                resource_type="application",
                resource_id=slug,
                client_ip=client_ip,
                metadata={"reason": reason},
            )
