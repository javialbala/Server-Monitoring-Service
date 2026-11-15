import pytest

from minipaas.agent.config import AgentSettings, ConfigError
from minipaas.common.secrets import TokenError


@pytest.fixture(autouse=True)
def base_env(monkeypatch):
    for name in ("MINIPAAS_INSTANCE", "MINIPAAS_PUBLISH_ADDRESS", "MINIPAAS_ENABLE_TEST_CATALOG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MINIPAAS_AGENT_TOKEN_FILE", "/run/secrets/x")


def test_defaults():
    settings = AgentSettings.from_env()
    assert settings.instance == "dev"
    assert settings.publish_address == "127.0.0.1"
    assert settings.enable_test_catalog is False


def test_custom_values(monkeypatch):
    monkeypatch.setenv("MINIPAAS_INSTANCE", "e2e")
    monkeypatch.setenv("MINIPAAS_PUBLISH_ADDRESS", "10.0.0.5")
    monkeypatch.setenv("MINIPAAS_ENABLE_TEST_CATALOG", "true")
    settings = AgentSettings.from_env()
    assert (settings.instance, settings.publish_address) == ("e2e", "10.0.0.5")
    assert settings.enable_test_catalog is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MINIPAAS_INSTANCE", "Mala Instancia"),
        ("MINIPAAS_PUBLISH_ADDRESS", "no-es-ip"),
        ("MINIPAAS_PUBLISH_ADDRESS", "::1"),
        ("MINIPAAS_ENABLE_TEST_CATALOG", "yes"),
    ],
)
def test_invalid_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError):
        AgentSettings.from_env()


def test_missing_token_file(monkeypatch):
    monkeypatch.delenv("MINIPAAS_AGENT_TOKEN_FILE")
    with pytest.raises(TokenError):
        AgentSettings.from_env()
