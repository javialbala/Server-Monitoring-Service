"""Migraciones numeradas: archivos `NNNN_nombre.sql` aplicados en orden."""

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Los .sql están bajo src/, así que viajan con el código en la imagen.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
FILE_PATTERN = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


class MigrationError(Exception):
    """Migraciones inválidas o base de datos incompatible con el código."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


def available_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    found: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = FILE_PATTERN.match(path.name)
        if not match:
            raise MigrationError(f"Nombre de migración inválido: {path.name} (usa NNNN_nombre.sql)")
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"Versión de migración duplicada: {version:04d}")
        found[version] = Migration(version, match.group(2), path)
    return [found[version] for version in sorted(found)]


def current_version(conn: sqlite3.Connection) -> int:
    """Versión instalada; 0 si la base de datos está vacía (no existe la tabla)."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if table is None:
        return 0
    return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]


def split_statements(sql: str) -> list[str]:
    """Divide el SQL en sentencias completas.

    No se usa `executescript` porque hace un COMMIT implícito y rompería la atomicidad
    de cada migración.
    """
    statements, buffer = [], ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        raise MigrationError("La migración termina con una sentencia incompleta (falta ';').")
    return [s for s in statements if s]


def _apply(conn: sqlite3.Connection, migration: Migration) -> bool:
    """Aplica una migración en su propia transacción. False si otro proceso ya la aplicó."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        # Se vuelve a leer DENTRO de la transacción: si dos procesos arrancan a la vez,
        # el segundo espera el bloqueo y aquí ve que el primero ya la aplicó.
        if current_version(conn) >= migration.version:
            conn.execute("ROLLBACK")
            return False
        for statement in split_statements(migration.path.read_text(encoding="utf-8")):
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, datetime.now(UTC).isoformat(timespec="seconds")),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return True


def migrate(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Aplica las migraciones pendientes y devuelve las versiones aplicadas."""
    migrations = available_migrations(directory)
    latest = migrations[-1].version if migrations else 0
    installed = current_version(conn)
    if installed > latest:
        raise MigrationError(
            f"La base de datos está en la versión {installed} y el código solo conoce "
            f"hasta la {latest}: la base de datos es más nueva que el código."
        )
    return [m.version for m in migrations if m.version > installed and _apply(conn, m)]
