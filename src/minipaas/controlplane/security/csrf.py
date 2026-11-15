"""Protección CSRF: comprobación de origen y token sincronizador.

`SameSite=Strict` no basta por sí solo: no cubre peticiones desde subdominios hermanos ni
navegadores antiguos. Por eso se añaden dos defensas:
  1. Origen: si la petición trae la cabecera `Origin`, debe ser el propio origen del panel.
  2. Token sincronizador: las peticiones autenticadas que modifican datos deben llevar en
     `X-CSRF-Token` el token de su sesión, que otra web no puede leer.
"""

import hmac

from fastapi import HTTPException, Request

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "X-CSRF-Token"


def check_origin(request: Request) -> None:
    """Dependencia global: rechaza los métodos no seguros (incluido el login) con Origin ajeno."""
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is None:
        return  # peticiones no hechas por un navegador (curl, scripts): sin cookie ajena que abusar
    own_origin = f"{request.url.scheme}://{request.url.netloc}"
    if origin != own_origin:
        raise HTTPException(status_code=403, detail="Origen de la petición no permitido")


def csrf_token_is_valid(expected: str, provided: str | None) -> bool:
    # compare_digest evita filtrar el token por diferencias de tiempo.
    return provided is not None and hmac.compare_digest(expected.encode(), provided.encode())
