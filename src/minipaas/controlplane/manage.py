"""CLI de administración: `python -m minipaas.controlplane.manage set-password`.

Se ejecuta dentro del contenedor del panel (sistema de archivos de solo lectura: solo escribe
en /data). La contraseña NUNCA se acepta como argumento, porque quedaría en el historial del
shell y sería visible con `ps`.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from minipaas.controlplane.config import DEFAULT_PASSWORD_HASH_FILE
from minipaas.controlplane.security.passwords import (
    WeakPassword,
    hash_password,
    validate_new_password,
)


def write_hash_file(path: str, password_hash: str) -> None:
    """Escribe el hash con permisos 600 y de forma atómica (archivo temporal + rename),
    para que el panel nunca lea un archivo a medias."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.unlink(missing_ok=True)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(password_hash + "\n")
    os.replace(temp, target)


def set_password(args: argparse.Namespace) -> int:
    if args.stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repite la contraseña: "):
            print("Error: las contraseñas no coinciden.", file=sys.stderr)
            return 1
    try:
        validate_new_password(password)
    except WeakPassword as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    path = os.environ.get("MINIPAAS_PASSWORD_HASH_FILE", DEFAULT_PASSWORD_HASH_FILE)
    write_hash_file(path, hash_password(password))
    print(f"Contraseña guardada en {path}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minipaas.controlplane.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("set-password", help="establece la contraseña del panel")
    command.add_argument(
        "--stdin",
        action="store_true",
        help="lee la contraseña de la entrada estándar (una línea) en vez de pedirla",
    )
    command.set_defaults(func=set_password)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
