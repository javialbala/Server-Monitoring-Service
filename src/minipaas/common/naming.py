"""Nombres, etiquetas y formatos compartidos por control plane y agente.

`minipaas.managed=true` se reserva para los recursos de las APLICACIONES de usuario: el agente
solo opera sobre recursos con esa etiqueta Y con la etiqueta de su propia instancia. Los
contenedores de la propia plataforma NO la llevan, precisamente para que el agente no pueda
pararse ni borrarse a sí mismo ni al control plane; se identifican con `minipaas.component`.

La «instancia» distingue dos instalaciones de MiniPaaS sobre el mismo Docker (p. ej. el entorno
de desarrollo `dev` y el de pruebas extremo a extremo `e2e`): ninguna toca los recursos de la otra.
"""

import re

RESOURCE_PREFIX = "minipaas-"

LABEL_MANAGED = "minipaas.managed"
LABEL_COMPONENT = "minipaas.component"
LABEL_INSTANCE = "minipaas.instance"
LABEL_APP = "minipaas.app"  # slug de la aplicación
LABEL_APP_ID = "minipaas.app_id"
LABEL_SERVICE = "minipaas.service"
LABEL_REVISION = "minipaas.revision"
LABEL_OPERATION = "minipaas.operation"
LABEL_CATALOG = "minipaas.catalog"
LABEL_INTERNAL_PORT = "minipaas.internal_port"
LABEL_ROLE = "minipaas.role"  # "service" | "probe" | "network-internal" | "network-edge"

# Formatos (validados en control plane Y en agente).
APP_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")
SERVICE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,28}[a-z0-9]$")
INSTANCE_RE = re.compile(r"^[a-z][a-z0-9]{1,15}$")
OPERATION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"  # UUID versión 4
)


def is_valid_slug(value: str) -> bool:
    return bool(APP_SLUG_RE.match(value)) and "--" not in value


def is_valid_service_name(value: str) -> bool:
    return bool(SERVICE_NAME_RE.match(value)) and "--" not in value


def internal_network_name(instance: str, app_slug: str) -> str:
    """Red interna de la aplicación: todos sus servicios, sin salida a Internet."""
    return f"{RESOURCE_PREFIX}{instance}-{app_slug}"


def edge_network_name(instance: str, app_slug: str) -> str:
    """Red de publicación: solo servicios con puerto publicado; sin NAT de salida (ADR-031)."""
    return f"{RESOURCE_PREFIX}{instance}-{app_slug}-edge"


def container_name(instance: str, app_slug: str, service_name: str, revision: int) -> str:
    """Nombre determinista: crear dos veces lo mismo no duplica contenedores (idempotencia)."""
    return f"{RESOURCE_PREFIX}{instance}-{app_slug}-{service_name}-r{revision}"
