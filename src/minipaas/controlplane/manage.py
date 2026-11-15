"""CLI de administración: `python -m minipaas.controlplane.manage <comando>`.

Se ejecuta dentro del contenedor del control plane (sistema de archivos de solo lectura:
solo escribe en /data). La contraseña NUNCA se acepta como argumento, porque quedaría en el
historial del shell y sería visible con `ps`.
"""

import argparse
import getpass
import os
import sys

from minipaas.controlplane.clock import utc_now
from minipaas.controlplane.config import DEFAULT_DB_PATH, ConfigError
from minipaas.controlplane.db import migrations
from minipaas.controlplane.db.connection import Database, transaction
from minipaas.controlplane.security.rate_limit import LoginRateLimiter
from minipaas.controlplane.security.sessions import SessionService
from minipaas.controlplane.services import audit
from minipaas.controlplane.services.audit import AuditService
from minipaas.controlplane.services.auth import AdminAlreadyExists, AuthService


def _database() -> Database:
    return Database(os.environ.get("MINIPAAS_DB_PATH", DEFAULT_DB_PATH))


def cmd_migrate(args: argparse.Namespace) -> int:
    db = _database()
    applied = db.initialize()
    if applied:
        conn = db.connect()
        try:
            with transaction(conn):
                AuditService().record(
                    conn,
                    audit.DATABASE_MIGRATE,
                    audit.SUCCESS,
                    metadata={"versions": ",".join(map(str, applied)), "source": "cli"},
                )
        finally:
            conn.close()
    conn = db.connect()
    try:
        version = migrations.current_version(conn)
        print(f"Migraciones aplicadas: {applied or 'ninguna'}. Versión actual: {version}")
    finally:
        conn.close()
    return 0


def cmd_db_version(args: argparse.Namespace) -> int:
    conn = _database().connect()
    try:
        installed = migrations.current_version(conn)
    finally:
        conn.close()
    latest = migrations.available_migrations()[-1].version
    print(f"Versión instalada: {installed}. Última disponible: {latest}.")
    return 0


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Contraseña: ")
    if first != getpass.getpass("Repite la contraseña: "):
        raise ValueError("Las contraseñas no coinciden.")
    return first


def cmd_create_admin(args: argparse.Namespace) -> int:
    db = _database()
    db.initialize()  # por si se ejecuta antes de que arranque el servidor
    try:
        password = _read_password(args.password_stdin)
        auth = AuthService(SessionService(1, 1), AuditService(), LoginRateLimiter(1, 1), utc_now)
        conn = db.connect()
        try:
            auth.create_admin(conn, args.username, password, source="cli")
        finally:
            conn.close()
    except AdminAlreadyExists:
        print("Ya existe un administrador; no se modifica.", file=sys.stderr)
        return 1
    except ValueError as error:  # contraseña débil, usuario inválido, no coinciden
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Administrador '{args.username}' creado.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minipaas.controlplane.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="aplica las migraciones pendientes").set_defaults(
        func=cmd_migrate
    )
    commands.add_parser("db-version", help="muestra la versión del esquema").set_defaults(
        func=cmd_db_version
    )
    create = commands.add_parser("create-admin", help="crea el administrador inicial")
    create.add_argument("--username", required=True)
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="lee la contraseña de la entrada estándar (una línea) en vez de pedirla",
    )
    create.set_defaults(func=cmd_create_admin)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, migrations.MigrationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
