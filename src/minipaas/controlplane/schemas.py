"""Modelos de entrada y salida de la API (Pydantic v2)."""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from minipaas.common.naming import OPERATION_ID_RE
from minipaas.controlplane.repositories.applications import Application
from minipaas.controlplane.services.app_lifecycle import RuntimeView
from minipaas.controlplane.services.app_services import ServiceChanges, ServiceView
from minipaas.controlplane.services.applications import validate_slug
from minipaas.controlplane.services.deployments import DeploymentView

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
    active_revision: int | None
    operation_in_progress: bool

    @classmethod
    def from_application(cls, application: Application) -> "ApplicationOut":
        data = {k: getattr(application, k) for k in cls.model_fields}
        return cls(**data)


class ApplicationList(BaseModel):
    items: list[ApplicationOut]


class ServiceCreate(BaseModel):
    model_config = _STRICT
    name: str
    catalog_id: str
    internal_port: int | None = None
    publish: bool = False
    host_port: int | None = None
    env: dict[str, str] = Field(default_factory=dict)
    memory_mb: int | None = None
    cpus: float | None = None


class ServiceUpdate(BaseModel):
    """Todos los campos son opcionales; `name` y `catalog_id` no se pueden cambiar."""

    model_config = _STRICT
    internal_port: int | None = None
    publish: bool | None = None
    host_port: int | None = None
    env: dict[str, str] | None = None
    memory_mb: int | None = None
    cpus: float | None = None

    @model_validator(mode="after")
    def require_some_field(self) -> "ServiceUpdate":
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo a modificar")
        return self

    def to_changes(self) -> ServiceChanges:
        publish = self.publish
        if publish is None and self.host_port is not None:
            publish = True  # indicar un puerto de acceso implica publicar
        return ServiceChanges(
            self.internal_port, publish, self.host_port, self.env, self.memory_mb, self.cpus
        )


class ServiceOut(BaseModel):
    name: str
    catalog_id: str
    catalog_name: str
    internal_port: int
    publish: bool
    host_port: int | None
    env: dict[str, str]
    memory_mb: int
    cpus: float
    created_at: str
    updated_at: str
    protected: bool

    @classmethod
    def from_view(cls, view: ServiceView) -> "ServiceOut":
        s = view.service
        return cls(
            name=s.name,
            catalog_id=s.catalog_id,
            catalog_name=view.catalog_name,
            internal_port=s.internal_port,
            publish=s.host_port is not None,
            host_port=s.host_port,
            env=s.env,
            memory_mb=s.memory_mb,
            cpus=s.cpus,
            created_at=s.created_at,
            updated_at=s.updated_at,
            protected=view.protected,
        )


class ServiceList(BaseModel):
    items: list[ServiceOut]


class RevisionCreate(BaseModel):
    model_config = _STRICT
    request_id: str = Field(pattern=OPERATION_ID_RE.pattern)  # UUID versión 4


class DeploymentServiceOut(BaseModel):
    """Servicio de una revisión. Solo los NOMBRES de las variables, nunca sus valores."""

    name: str
    catalog_id: str
    catalog_name: str
    image_ref: str
    internal_port: int
    host_port: int | None
    memory_mb: int
    cpus: float
    env_names: list[str]


class DeploymentEventOut(BaseModel):
    occurred_at: str
    step: str
    outcome: str
    message: str


class DeploymentOut(BaseModel):
    revision: int
    operation_id: str
    status: str
    status_label: str
    is_active: bool
    previous_revision: int | None
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    services: list[DeploymentServiceOut]

    @classmethod
    def from_view(cls, view: DeploymentView, catalog_name) -> "DeploymentOut":
        d = view.deployment
        data = {k: getattr(d, k) for k in cls.model_fields if k != "services"}
        services = [
            DeploymentServiceOut(
                name=s.service_name,
                catalog_id=s.catalog_id,
                catalog_name=catalog_name(s.catalog_id),
                image_ref=s.image_ref,
                internal_port=s.internal_port,
                host_port=s.host_port,
                memory_mb=s.memory_mb,
                cpus=s.cpus,
                env_names=sorted(s.env),
            )
            for s in view.services
        ]
        return cls(**data, services=services)


class DeploymentDetailOut(DeploymentOut):
    events: list[DeploymentEventOut]


class DeploymentList(BaseModel):
    items: list[DeploymentOut]


class RuntimeServiceOut(BaseModel):
    name: str
    revision: int
    state: str
    state_label: str
    exit_code: int | None
    host_port: int | None
    access_url: str | None


class RuntimeOut(BaseModel):
    agent_reachable: bool
    active_revision: int | None
    services: list[RuntimeServiceOut]
    unknown_containers: int

    @classmethod
    def from_view(cls, view: RuntimeView) -> "RuntimeOut":
        services = [
            RuntimeServiceOut(
                name=s.container.service_name,
                revision=s.container.revision,
                state=s.container.state,
                state_label=s.state_label,
                exit_code=s.container.exit_code,
                host_port=s.container.host_port,
                access_url=s.access_url,
            )
            for s in view.services
        ]
        return cls(
            agent_reachable=view.agent_reachable,
            active_revision=view.active_revision,
            services=services,
            unknown_containers=view.unknown_containers,
        )
