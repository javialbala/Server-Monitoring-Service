"""Lectura de los contenedores en ejecución. Solo consultas: nunca modifica nada."""

from datetime import UTC, datetime

from docker import DockerClient


def docker_status(client: DockerClient) -> dict:
    """Estado del daemon para /health. Cualquier fallo significa "no accesible"."""
    try:
        version = client.version()
        return {"reachable": True, "server_version": str(version.get("Version"))}
    except Exception:  # noqa: BLE001 - docker y requests lanzan excepciones distintas
        return {"reachable": False, "server_version": None}


def _convert_ports(raw_ports: list[dict]) -> list[dict]:
    ports = []
    for port in raw_ports:
        ports.append(
            {
                "container_port": port["PrivatePort"],
                "protocol": port.get("Type", "tcp"),
                "host_ip": port.get("IP"),  # None si el puerto no está publicado
                "host_port": port.get("PublicPort"),
            }
        )
    return ports


def list_running_containers(client: DockerClient) -> list[dict]:
    """Una sola llamada de solo lectura a Docker; lanza excepción si Docker falla."""
    raw_containers = client.api.containers(filters={"status": "running"})
    containers = []
    for raw in raw_containers:
        labels = raw.get("Labels") or {}
        created = datetime.fromtimestamp(raw["Created"], UTC)
        containers.append(
            {
                "id": raw["Id"][:12],
                "name": raw["Names"][0].lstrip("/") if raw.get("Names") else raw["Id"][:12],
                "image": raw["Image"],
                "state": raw["State"],
                "status": raw["Status"],
                "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ports": _convert_ports(raw.get("Ports") or []),
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
            }
        )
    return sorted(containers, key=lambda container: container["name"])
