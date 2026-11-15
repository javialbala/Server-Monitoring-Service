"""Doble de prueba del SDK de Docker: contenedores, redes e imágenes en memoria.

Simula solo lo que usa `AgentOperations`, con las mismas formas de datos que el SDK real
(`attrs`, `labels`, excepciones de `docker.errors`). Así las pruebas no necesitan Docker.
"""

import docker.errors

from minipaas.agent.docker_runtime import DockerStatus
from minipaas.common.catalog import NGINX_STATIC, WHOAMI


class FakeContainer:
    def __init__(self, client, name, labels, kwargs):
        self.client = client
        self.name = name
        self.labels = labels
        self.create_kwargs = kwargs
        self.networks: list[str] = []
        self.status = "created"
        self.exit_code = 0
        self.start_error: Exception | None = None
        self.wait_exit_code = 0  # para sondas
        self.removed = False
        bindings = {
            port: [{"HostIp": ip, "HostPort": str(host_port)}]
            for port, (ip, host_port) in (kwargs.get("ports") or {}).items()
        }
        self._bindings = bindings

    @property
    def attrs(self):
        return {
            "State": {
                "Status": self.status,
                "ExitCode": self.exit_code,
                "OOMKilled": False,
                "StartedAt": "2030-01-01T00:00:00Z" if self.status == "running" else "0001-01-01",
            },
            "RestartCount": 0,
            "HostConfig": {"PortBindings": self._bindings},
        }

    def reload(self):
        pass

    def start(self):
        if self.start_error:
            raise self.start_error
        self.status = "running"

    def stop(self, timeout=None):
        self.status = "exited"

    def wait(self, timeout=None):
        return {"StatusCode": self.wait_exit_code}

    def remove(self, force=False):
        self.removed = True
        for net in self.client.network_objs.values():
            net.containers.discard(self.name)
        self.client.container_objs.pop(self.name, None)


class FakeNetwork:
    def __init__(self, name, labels, options=None, internal=False):
        self.attrs = {"Name": name, "Labels": labels, "Containers": {}, "Internal": internal}
        self.options = options
        self.containers: set[str] = set()

    def reload(self):
        self.attrs["Containers"] = {name: {} for name in self.containers}

    def connect(self, container):
        self.containers.add(container.name)
        container.networks.append(self.attrs["Name"])

    def remove(self):
        self.client.network_objs.pop(self.attrs["Name"], None)


class _Containers:
    def __init__(self, client):
        self.client = client

    def get(self, name):
        try:
            return self.client.container_objs[name]
        except KeyError:
            raise docker.errors.NotFound("no such container") from None

    def create(self, image, **kwargs):
        name = kwargs["name"]
        container = FakeContainer(self.client, name, kwargs.get("labels") or {}, kwargs)
        container.image = image
        self.client.container_objs[name] = container
        self.client.created.append(container)
        network = self.client.network_objs.get(kwargs.get("network"))
        if network is not None:
            network.connect(container)
        return container

    def list(self, all=False, filters=None):
        wanted = dict(item.split("=", 1) for item in (filters or {}).get("label", []))
        return [
            c
            for c in self.client.container_objs.values()
            if all and wanted.items() <= c.labels.items()
        ]


class _Networks:
    def __init__(self, client):
        self.client = client

    def get(self, name):
        try:
            return self.client.network_objs[name]
        except KeyError:
            raise docker.errors.NotFound("no such network") from None

    def create(self, name, driver="bridge", internal=False, options=None, labels=None):
        network = FakeNetwork(name, labels, options, internal)
        network.client = self.client
        self.client.network_objs[name] = network
        return network


class _Image:
    def __init__(self, digests):
        self.attrs = {"RepoDigests": digests}


class _Images:
    def __init__(self, client):
        self.client = client

    def get(self, ref):
        if ref not in self.client.image_objs:
            raise docker.errors.ImageNotFound("no such image")
        return _Image(self.client.image_objs[ref])

    def pull(self, ref):
        self.client.pulled.append(ref)
        self.client.image_objs[ref] = [ref]


class _Api:
    @staticmethod
    def create_endpoint_config(aliases=None):
        return {"Aliases": aliases}


class FakeClient:
    def __init__(self, architecture="x86_64"):
        self.architecture = architecture
        self.container_objs: dict[str, FakeContainer] = {}
        self.network_objs: dict[str, FakeNetwork] = {}
        self.image_objs = {e.image_ref: [e.image_ref] for e in (NGINX_STATIC, WHOAMI)}
        self.created: list[FakeContainer] = []
        self.pulled: list[str] = []
        self.containers = _Containers(self)
        self.networks = _Networks(self)
        self.images = _Images(self)
        self.api = _Api()

    def info(self):
        return {"Architecture": self.architecture}


class FakeRuntime:
    """Sustituye a DockerRuntime. `error` hace fallar cualquier acceso al cliente."""

    def __init__(self, status: DockerStatus | None = None):
        self.fake = FakeClient()
        self.status = status or DockerStatus(reachable=True, server_version="29.0.0")
        self.error: Exception | None = None

    def client(self):
        if self.error:
            raise self.error
        return self.fake

    def ping(self) -> DockerStatus:
        return self.status
