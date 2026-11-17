from datetime import UTC, datetime

from docker import DockerClient


def docker_status(client: DockerClient) -> dict:
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


def _health_from_status(status: str) -> str | None:
    """Docker escribe la salud en el texto de estado: "Up 3 hours (healthy)"."""
    if "(unhealthy)" in status:  # se mira antes que "(healthy)"
        return "unhealthy"
    if "(healthy)" in status:
        return "healthy"
    if "(health: starting)" in status:
        return "starting"
    return None


def list_containers(client: DockerClient) -> list[dict]:
    raw_containers = client.api.containers(all=True)
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
                "health": _health_from_status(raw["Status"]),
                "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ports": _convert_ports(raw.get("Ports") or []),
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
            }
        )
    # En ejecución primero; dentro de cada grupo, por nombre.
    return sorted(containers, key=lambda c: (c["state"] != "running", c["name"]))
