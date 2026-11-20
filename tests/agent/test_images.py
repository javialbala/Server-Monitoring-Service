from fakes import FakeDockerClient

from server_monitor.agent import images


def raw_image(reference, size=1024, containers=0):
    return {
        "Id": f"{reference}:" + "i" * 64,
        "RepoTags": [reference],
        "Created": 1777600000,
        "Size": size,
        "Containers": containers,
    }


def test_list_images_converts_tags_and_sorts_by_size():
    raw = [
        raw_image("ghcr.io/example/app:latest", size=2048, containers=1),
        raw_image("postgres:16", size=4096),
        raw_image("localhost:5000/team/api:1.0", size=1024),
    ]
    client = FakeDockerClient(images=raw)
    result = images.list_images(client)

    assert client.api.calls == [("images", {})]
    assert [(image["repository"], image["tag"]) for image in result] == [
        ("postgres", "16"),
        ("ghcr.io/example/app", "latest"),
        ("localhost:5000/team/api", "1.0"),
    ]
    assert result[0]["size_bytes"] == 4096
    assert result[1]["in_use"] is True
    assert result[2]["created_at"].endswith("Z")


def test_list_images_handles_dangling_images():
    raw = [{"Id": "d" * 64, "RepoTags": ["<none>:<none>"], "Size": 0, "Containers": 0}]
    result = images.list_images(FakeDockerClient(images=raw))
    assert result[0]["repository"] == "<none>"
    assert result[0]["tag"] == "<none>"
    assert result[0]["in_use"] is False
