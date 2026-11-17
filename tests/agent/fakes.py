class FakeDockerApi:
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
    """Solo permite api.containers y version; cualquier otra llamada hace fallar el test."""

    def __init__(self, containers=None, error=None):
        self.api = FakeDockerApi(containers, error)
        self.error = error

    def version(self):
        if self.error:
            raise self.error
        return {"Version": "27.0.1"}

    def __getattr__(self, name):
        raise AssertionError(f"El agente llamó a una operación no permitida: client.{name}")
