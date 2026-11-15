"""Conexiones a SQLite con la configuración de seguridad y concurrencia del proyecto."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from minipaas.controlplane.db import migrations


class Database:
    def __init__(self, path: str | Path, migrations_dir: Path = migrations.MIGRATIONS_DIR) -> None:
        self.path = Path(path)
        self.migrations_dir = migrations_dir

    def connect(self) -> sqlite3.Connection:
        """Abre una conexión nueva. Quien la abre la cierra."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.path,
            timeout=5,
            # Autocommit: las transacciones son SIEMPRE explícitas (ver `transaction`).
            isolation_level=None,
            # FastAPI puede ejecutar la dependencia y el endpoint en hilos distintos del
            # threadpool. Cada conexión la usa una única petición, nunca dos a la vez.
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        # No persiste en el archivo: hay que activarlo en cada conexión.
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> list[int]:
        """Prepara la base de datos y aplica migraciones. Devuelve las aplicadas."""
        conn = self.connect()
        try:
            # WAL (persistente en el archivo): los lectores no bloquean al escritor.
            conn.execute("PRAGMA journal_mode=WAL")
            return migrations.migrate(conn, self.migrations_dir)
        finally:
            conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacción explícita: COMMIT si todo va bien, ROLLBACK ante cualquier excepción."""
    # IMMEDIATE toma el bloqueo de escritura desde el principio: evita el error
    # "database is locked" al intentar promocionar una lectura a escritura a mitad.
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
