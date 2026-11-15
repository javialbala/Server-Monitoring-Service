"""Hash y verificación de contraseñas con Argon2id."""

import threading

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

# Parámetros por defecto de argon2-cffi (perfil de bajo consumo de memoria del RFC 9106):
# variante Argon2id, 3 iteraciones, 64 MiB de memoria y 4 hilos. Cada verificación cuesta
# unos 64 MiB durante unas decenas de milisegundos: es lo que hace cara la fuerza bruta,
# y por eso el login lleva limitación de intentos (un atacante no puede lanzar miles a la vez).
_hasher = PasswordHasher()

# Como mucho 2 hashes a la vez: cada uno usa 64 MiB y, sin este límite, muchos logins
# simultáneos podrían agotar la memoria del contenedor (presupuesto de RAM del proyecto).
_slots = threading.BoundedSemaphore(2)

# Hash de una contraseña que nadie conoce. Se verifica cuando el usuario NO existe para que
# la respuesta tarde lo mismo y no se pueda averiguar qué usuarios existen midiendo tiempos.
DUMMY_HASH = _hasher.hash("contraseña-ficticia-que-nadie-usa")


class WeakPassword(ValueError):
    """La contraseña nueva no cumple la política de longitud."""


def validate_new_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise WeakPassword(
            f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y {MAX_PASSWORD_LENGTH} "
            "caracteres."
        )


def hash_password(password: str) -> str:
    with _slots:
        return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        with _slots:
            return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True si el hash se hizo con parámetros más débiles que los actuales."""
    return _hasher.check_needs_rehash(password_hash)
