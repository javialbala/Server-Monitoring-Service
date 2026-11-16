"""Contraseña única del panel: validación, hash Argon2id y lectura del archivo de hash."""

from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 4
MAX_PASSWORD_LENGTH = 128

# Parámetros por defecto de argon2-cffi: variante Argon2id, 3 iteraciones, 64 MiB de memoria.
# Hacen cara la fuerza bruta; por eso el login lleva además un límite de intentos fallidos.
_hasher = PasswordHasher()


class WeakPassword(ValueError):
    """La contraseña nueva no cumple la política de longitud."""


def validate_new_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise WeakPassword(
            f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y {MAX_PASSWORD_LENGTH} "
            "caracteres."
        )


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):  # VerifyMismatchError es un VerificationError
        return False


def read_hash_file(path: str) -> str | None:
    """Hash guardado, o None si todavía no se ha configurado la contraseña."""
    try:
        return Path(path).read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None
