import hmac

from fastapi import HTTPException, Request

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "X-CSRF-Token"


def check_origin(request: Request) -> None:
    """Rechaza los métodos no seguros con un Origin que no sea el del propio panel."""
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is None:
        return  # no es un navegador (curl, scripts)
    if origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(status_code=403, detail="Origen de la petición no permitido")


def csrf_token_is_valid(expected: str, provided: str | None) -> bool:
    return provided is not None and hmac.compare_digest(expected.encode(), provided.encode())
