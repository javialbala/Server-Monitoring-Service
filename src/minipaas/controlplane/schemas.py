"""Modelos de entrada y salida de la API (Pydantic v2)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.services.applications import validate_slug

# Las entradas rechazan campos desconocidos (extra="forbid"): p. ej. un "slug" en PATCH.
_STRICT = ConfigDict(extra="forbid")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class LoginRequest(BaseModel):
    model_config = _STRICT
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    # La contraseña NO se recorta: los espacios pueden formar parte de ella.
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class ApplicationCreate(BaseModel):
    model_config = _STRICT
    name: Name
    slug: str | None = None
    description: Description = ""

    @field_validator("slug")
    @classmethod
    def check_slug(cls, value: str | None) -> str | None:
        return None if value is None else validate_slug(value)


class ApplicationUpdate(BaseModel):
    model_config = _STRICT
    name: Name | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def require_some_field(self) -> "ApplicationUpdate":
        if self.name is None and self.description is None:
            raise ValueError("Indica al menos un campo a modificar (name o description)")
        return self


class UserOut(BaseModel):
    username: str


class MeOut(BaseModel):
    username: str
    created_at: str


class SessionOut(BaseModel):
    authenticated: bool
    setup_required: bool
    user: UserOut | None
    csrf_token: str | None


class LoginOut(BaseModel):
    user: UserOut
    csrf_token: str


class ApplicationOut(BaseModel):
    """Vista pública de una aplicación: sin el id interno."""

    slug: str
    name: str
    description: str
    status: str
    status_label: str
    created_at: str
    updated_at: str

    @classmethod
    def from_application(cls, application: Application) -> "ApplicationOut":
        data = {k: getattr(application, k) for k in cls.model_fields}
        return cls(**data)


class ApplicationList(BaseModel):
    items: list[ApplicationOut]
