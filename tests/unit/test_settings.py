import pytest

from minipaas.agent.config import AgentSettings
from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError
from minipaas.controlplane.config import ControlPlaneSettings


def test_controlplane_defaults(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/run/secrets/agent_token")
    monkeypatch.delenv("MINIPAAS_AGENT_URL", raising=False)
    settings = ControlPlaneSettings.from_env()
    assert settings.agent_url == "http://agent:8001"
    assert settings.agent_timeout == 3.0
    assert settings.token_file == "/run/secrets/agent_token"


def test_agent_settings(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/x")
    assert AgentSettings.from_env().token_file == "/x"


@pytest.mark.parametrize("settings_class", [AgentSettings, ControlPlaneSettings])
def test_settings_require_token_path(monkeypatch, settings_class):
    monkeypatch.delenv(TOKEN_FILE_ENV, raising=False)
    with pytest.raises(TokenError):
        settings_class.from_env()
