"""Catálogo cerrado de imágenes autorizadas (ADR-026 y ADR-027).

Es la ÚNICA fuente de imágenes que MiniPaaS puede descargar y ejecutar. El usuario elige una
entrada por su identificador; nunca escribe un nombre de imagen. Cada imagen está fijada por el
digest SHA-256 de su índice multiarquitectura: Docker comprueba al descargar que el contenido
coincide, de modo que la imagen no puede cambiar aunque alguien modifique la etiqueta en el
registro.

El control plane y el agente importan este módulo y validan cada uno por su cuenta (el agente no
confía en lo que le llega del control plane). Los digest se comprobaron con
`docker manifest inspect` y `docker pull` el 2026-11-15.
"""

import re
from dataclasses import dataclass

# Rango reservado para publicar puertos de aplicaciones en el host (ADR-008).
HOST_PORT_MIN = 20000
HOST_PORT_MAX = 20999

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# Ruta DENTRO del contenedor montada como tmpfs (memoria): no es un archivo temporal del host,
# por eso no aplica el aviso S108 de bandit.
CONTAINER_TMP = "/tmp"  # noqa: S108


class CatalogError(ValueError):
    """Configuración no permitida por el catálogo. El mensaje se puede mostrar al usuario."""


@dataclass(frozen=True)
class EnvVarSpec:
    """Variable de entorno que una imagen admite. Ninguna otra variable se acepta."""

    name: str
    label: str
    help: str
    pattern: str  # expresión regular que debe cumplir el valor completo
    max_length: int = 64


@dataclass(frozen=True)
class ResourceRange:
    default: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class HealthCheck:
    """Comprobación HTTP que hace una sonda desde la red interna de la aplicación (ADR-030).

    Se considera sano si `GET http://<servicio>:<puerto interno><path>` responde 2xx o 3xx.
    """

    path: str
    timeout_seconds: int = 3  # por intento
    interval_seconds: int = 2  # entre intentos
    max_wait_seconds: int = 45  # plazo total para que el servicio esté disponible


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    description: str
    repository: str
    version: str  # informativa: la referencia que se usa es el digest
    digest: str
    architectures: tuple[str, ...]
    internal_ports: tuple[int, ...]
    default_internal_port: int
    publishable: bool  # si puede publicar un puerto en el host
    env: tuple[EnvVarSpec, ...]
    health: HealthCheck
    memory_mb: ResourceRange
    cpus: ResourceRange
    pids_limit: int  # fijo, no lo elige el usuario
    user: str  # UID:GID no root con el que se ejecuta
    tmpfs: tuple[tuple[str, int], ...]  # (ruta, MiB) de almacenamiento temporal en memoria
    license: str
    source: str
    limitations: str
    test_only: bool = False  # solo se habilita con MINIPAAS_ENABLE_TEST_CATALOG=true

    @property
    def image_ref(self) -> str:
        """Referencia inmutable `repositorio@sha256:...` (nunca una etiqueta)."""
        return f"{self.repository}@{self.digest}"

    def env_spec(self, name: str) -> EnvVarSpec | None:
        return next((spec for spec in self.env if spec.name == name), None)


_NGINX_REPOSITORY = "nginxinc/nginx-unprivileged"
_NGINX_VERSION = "1.29.8-alpine"
_NGINX_DIGEST = "sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6"
_NGINX_ARCHITECTURES = ("amd64", "arm64", "arm/v7", "arm/v6", "386", "ppc64le", "riscv64", "s390x")
_NGINX_LICENSE = (
    "Imagen: Apache-2.0 (Dockerfiles de nginx/docker-nginx-unprivileged); NGINX: BSD-2-Clause; "
    "Alpine Linux y sus paquetes: licencias de cada proyecto"
)

NGINX_STATIC = CatalogEntry(
    id="nginx-static",
    name="Servidor web estático (NGINX)",
    description=(
        "Servidor web NGINX sin privilegios. En esta versión muestra la página de bienvenida de "
        "NGINX: todavía no se pueden añadir archivos propios (requiere volúmenes, Fase 6)."
    ),
    repository=_NGINX_REPOSITORY,
    version=_NGINX_VERSION,
    digest=_NGINX_DIGEST,
    architectures=_NGINX_ARCHITECTURES,
    internal_ports=(8080,),
    default_internal_port=8080,
    publishable=True,
    env=(),
    health=HealthCheck(path="/"),
    memory_mb=ResourceRange(default=64, minimum=32, maximum=256),
    cpus=ResourceRange(default=0.5, minimum=0.1, maximum=1.0),
    pids_limit=64,
    user="101:101",
    # NGINX escribe su PID y ficheros temporales en /tmp: con la raíz en solo lectura necesita
    # este almacenamiento temporal en memoria (se pierde al parar el contenedor).
    tmpfs=((CONTAINER_TMP, 32),),
    license=_NGINX_LICENSE,
    source="https://github.com/nginx/docker-nginx-unprivileged",
    limitations="Sin contenido propio hasta la Fase 6 (volúmenes). Sin HTTPS propio.",
)

WHOAMI = CatalogEntry(
    id="whoami",
    name="Servicio HTTP de prueba (whoami)",
    description=(
        "Pequeño servidor web que responde con datos de la petición y del contenedor. Sirve para "
        "comprobar el despliegue, el acceso desde el navegador y la comunicación entre servicios."
    ),
    repository="traefik/whoami",
    version="v1.11.0",
    digest="sha256:200689790a0a0ea48ca45992e0450bc26ccab5307375b41c84dfc4f2475937ab",
    architectures=("amd64", "arm64", "arm/v7"),
    internal_ports=(80,),
    default_internal_port=80,
    publishable=True,
    env=(
        EnvVarSpec(
            name="WHOAMI_NAME",
            label="Nombre mostrado",
            help="Texto que el servicio incluye en sus respuestas (letras, números, . _ -).",
            pattern=r"[A-Za-z0-9 ._-]{1,40}",
            max_length=40,
        ),
    ),
    health=HealthCheck(path="/health"),
    memory_mb=ResourceRange(default=32, minimum=16, maximum=128),
    cpus=ResourceRange(default=0.25, minimum=0.1, maximum=0.5),
    pids_limit=32,
    # La imagen no define usuario (sería root): se fuerza el usuario «nobody». Puede escuchar en
    # el puerto 80 sin privilegios porque Docker permite puertos bajos dentro del contenedor.
    user="65534:65534",
    tmpfs=(),
    license="Apache-2.0",
    source="https://github.com/traefik/whoami",
    limitations="Solo para pruebas y demostraciones; no guarda datos.",
)

# --- Entradas de prueba: provocan fallos controlados en los tests y en el E2E -------------
# Nunca aparecen salvo que control plane y agente tengan MINIPAAS_ENABLE_TEST_CATALOG=true.

TEST_CRASH = CatalogEntry(
    id="test-crash",
    name="[Prueba] Fallo al arrancar",
    description="NGINX sin su almacenamiento temporal: termina con error al arrancar.",
    repository=_NGINX_REPOSITORY,
    version=_NGINX_VERSION,
    digest=_NGINX_DIGEST,
    architectures=_NGINX_ARCHITECTURES,
    internal_ports=(8080,),
    default_internal_port=8080,
    publishable=True,
    env=(),
    health=HealthCheck(path="/", max_wait_seconds=20),
    memory_mb=ResourceRange(default=64, minimum=32, maximum=128),
    cpus=ResourceRange(default=0.25, minimum=0.1, maximum=0.5),
    pids_limit=64,
    user="101:101",
    tmpfs=(),  # a propósito: «mkdir() /tmp/proxy_temp failed (Read-only file system)»
    license=_NGINX_LICENSE,
    source="https://github.com/nginx/docker-nginx-unprivileged",
    limitations="Solo para pruebas de fallo y recuperación.",
    test_only=True,
)

TEST_UNHEALTHY = CatalogEntry(
    id="test-unhealthy",
    name="[Prueba] Arranca pero no está disponible",
    description="NGINX funcionando, pero su comprobación de salud pide una ruta inexistente (404).",
    repository=_NGINX_REPOSITORY,
    version=_NGINX_VERSION,
    digest=_NGINX_DIGEST,
    architectures=_NGINX_ARCHITECTURES,
    internal_ports=(8080,),
    default_internal_port=8080,
    publishable=True,
    env=(),
    health=HealthCheck(path="/__minipaas_ruta_inexistente", max_wait_seconds=12),
    memory_mb=ResourceRange(default=64, minimum=32, maximum=128),
    cpus=ResourceRange(default=0.25, minimum=0.1, maximum=0.5),
    pids_limit=64,
    user="101:101",
    tmpfs=((CONTAINER_TMP, 32),),
    license=_NGINX_LICENSE,
    source="https://github.com/nginx/docker-nginx-unprivileged",
    limitations="Solo para pruebas de fallo y recuperación.",
    test_only=True,
)

_ALL_ENTRIES = (NGINX_STATIC, WHOAMI, TEST_CRASH, TEST_UNHEALTHY)

# Imagen de la sonda de salud: la misma de NGINX (contiene busybox `wget`), así no se descarga
# nada más. La sonda la construye y ejecuta el agente, nunca el usuario (ADR-030).
PROBE_IMAGE_REF = NGINX_STATIC.image_ref
PROBE_USER = "101:101"


def enabled_entries(include_test: bool) -> tuple[CatalogEntry, ...]:
    return tuple(entry for entry in _ALL_ENTRIES if include_test or not entry.test_only)


def get_entry(catalog_id: str, include_test: bool) -> CatalogEntry:
    for entry in enabled_entries(include_test):
        if entry.id == catalog_id:
            return entry
    raise CatalogError(f"El servicio «{catalog_id}» no está en el catálogo autorizado.")


def docker_architecture(machine: str) -> str:
    """Traduce la arquitectura que informa Docker (`docker info`) al nombre de los manifiestos."""
    return {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "arm/v7",
        "armv6l": "arm/v6",
        "i386": "386",
        "i686": "386",
    }.get(machine, machine)


@dataclass(frozen=True)
class ServiceConfig:
    """Configuración de un servicio ya validada contra su entrada del catálogo."""

    catalog_id: str
    internal_port: int
    host_port: int | None  # None: no se publica en el host
    env: tuple[tuple[str, str], ...]  # ordenado por nombre
    memory_mb: int
    cpus: float

    def env_dict(self) -> dict[str, str]:
        return dict(self.env)


def validate_service_config(
    entry: CatalogEntry,
    *,
    internal_port: int | None,
    host_port: int | None,
    env: dict[str, str] | None,
    memory_mb: int | None,
    cpus: float | None,
    architecture: str | None = None,
) -> ServiceConfig:
    """Valida la configuración de un servicio y devuelve la versión normalizada.

    Los valores omitidos toman el valor por defecto del catálogo. Lanza CatalogError con un
    mensaje comprensible si algo no está permitido. `architecture` (formato de manifiesto,
    p. ej. "amd64") solo lo pasa el agente, que es quien conoce el host.
    """
    if architecture is not None and architecture not in entry.architectures:
        raise CatalogError(
            f"La imagen de «{entry.name}» no está disponible para la arquitectura {architecture}."
        )
    if not DIGEST_RE.match(entry.digest):
        raise CatalogError(f"La entrada «{entry.id}» no tiene un digest SHA-256 válido.")

    port = entry.default_internal_port if internal_port is None else internal_port
    if port not in entry.internal_ports:
        allowed = ", ".join(map(str, entry.internal_ports))
        raise CatalogError(f"Puerto interno no permitido (permitidos: {allowed}).")

    if host_port is not None:
        if not entry.publishable:
            raise CatalogError("Este servicio no puede publicar puertos en el host.")
        if not HOST_PORT_MIN <= host_port <= HOST_PORT_MAX:
            raise CatalogError(
                f"El puerto de acceso debe estar entre {HOST_PORT_MIN} y {HOST_PORT_MAX}."
            )

    clean_env: dict[str, str] = {}
    for name, value in (env or {}).items():
        spec = entry.env_spec(name)
        if spec is None:
            raise CatalogError(f"La variable «{name}» no está permitida para este servicio.")
        if not isinstance(value, str) or len(value) > spec.max_length:
            raise CatalogError(f"El valor de «{spec.label}» es demasiado largo.")
        if not re.fullmatch(spec.pattern, value):
            raise CatalogError(f"El valor de «{spec.label}» no es válido. {spec.help}")
        clean_env[name] = value

    memory = int(entry.memory_mb.default if memory_mb is None else memory_mb)
    if not entry.memory_mb.minimum <= memory <= entry.memory_mb.maximum:
        raise CatalogError(
            f"La memoria debe estar entre {int(entry.memory_mb.minimum)} y "
            f"{int(entry.memory_mb.maximum)} MiB."
        )
    cpu = round(float(entry.cpus.default if cpus is None else cpus), 2)
    if not entry.cpus.minimum <= cpu <= entry.cpus.maximum:
        raise CatalogError(
            f"La CPU debe estar entre {entry.cpus.minimum} y {entry.cpus.maximum} núcleos."
        )

    return ServiceConfig(
        catalog_id=entry.id,
        internal_port=port,
        host_port=host_port,
        env=tuple(sorted(clean_env.items())),
        memory_mb=memory,
        cpus=cpu,
    )
