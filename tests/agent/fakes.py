"""Clientes Docker falsos que solo permiten consultas."""

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeDockerApi:
    """Imita client.api: solo `containers` (consulta). Cualquier otra cosa falla."""

    def __init__(self, containers=None, error=None):
        self.containers_result = containers or []
        self.error = error
        self.calls = []

    def containers(self, **kwargs):
        self.calls.append(("containers", kwargs))
        if self.error:
            raise self.error
        return self.containers_result

    def __getattr__(self, name):
        raise AssertionError(f"El agente llamó a una operación no permitida: api.{name}")


class FakeDockerClient:
    """Solo permite consultas: api.containers y version. Todo lo demás hace fallar el test."""

    def __init__(self, containers=None, error=None):
        self.api = FakeDockerApi(containers, error)
        self.error = error

    def version(self):
        if self.error:
            raise self.error
        return {"Version": "27.0.1"}

    def __getattr__(self, name):
        raise AssertionError(f"El agente llamó a una operación no permitida: client.{name}")
