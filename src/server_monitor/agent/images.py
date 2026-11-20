from datetime import UTC, datetime

from docker import DockerClient


def _split_reference(reference: str) -> tuple[str, str]:
    """Separa repositorio y etiqueta; admite registros con puerto y digests."""
    if not reference or reference in ("<none>", "<none>:<none>"):
        return "<none>", "<none>"
    if "@" in reference:
        repository, _, digest = reference.partition("@")
        return repository, digest
    last_slash = reference.rfind("/")
    last_colon = reference.rfind(":")
    if last_colon > last_slash:
        return reference[:last_colon], reference[last_colon + 1 :]
    return reference, "latest"


def list_images(client: DockerClient) -> list[dict]:
    raw_images = client.api.images()
    images = []
    for raw in raw_images:
        tags = raw.get("RepoTags") or []
        primary = next(
            (tag for tag in tags if tag and not tag.startswith("<none>")),
            tags[0] if tags else "<none>:<none>",
        )
        repository, tag = _split_reference(primary)
        created = raw.get("Created")
        images.append(
            {
                "id": str(raw.get("Id", ""))[:12],
                "repository": repository,
                "tag": tag,
                "size_bytes": int(raw.get("Size") or 0),
                "created_at": (
                    datetime.fromtimestamp(created, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if created
                    else None
                ),
                "in_use": int(raw.get("Containers") or 0) > 0,
            }
        )
    # Las imágenes más grandes primero; a igualdad, por nombre y etiqueta.
    return sorted(
        images, key=lambda image: (-image["size_bytes"], image["repository"], image["tag"])
    )
