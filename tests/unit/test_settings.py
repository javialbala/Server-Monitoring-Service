import pytest

from minipaas.agent.config import AgentSettings
from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError
from minipaas.controlplane.config import ConfigError, ControlPlaneSettings


def test_controlplane_defaults(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/run/secrets/agent_token")
    monkeypatch.delenv("MINIPAAS_AGENT_URL", raising=False)
    settings = ControlPlaneSettings.from_env()
    assert settings.agent_url == "http://agent:8001"
    assert settings.agent_timeout == 3.0
    assert settings.token_file == "/run/secrets/agent_token"
    assert settings.db_path == "/data/minipaas.sqlite3"
    assert settings.cookie_secure is False
    assert (settings.session_idle_minutes, settings.session_absolute_hours) == (30, 8)
    assert (settings.login_max_failures, settings.login_window_minutes) == (5, 15)


def test_controlplane_env_overrides(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/x")
    monkeypatch.setenv("MINIPAAS_DB_PATH", "/srv/otra.sqlite3")
    monkeypatch.setenv("MINIPAAS_COOKIE_SECURE", "TRUE")
    settings = ControlPlaneSettings.from_env()
    assert settings.db_path == "/srv/otra.sqlite3"
    assert settings.cookie_secure is True


def test_invalid_numbers_are_rejected():
    with pytest.raises(ConfigError):
        ControlPlaneSettings(agent_url="x", token_file="y", login_max_failures=0)


def test_agent_settings(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/x")
    assert AgentSettings.from_env().token_file == "/x"


@pytest.mark.parametrize("settings_class", [AgentSettings, ControlPlaneSettings])
def test_settings_require_token_path(monkeypatch, settings_class):
    monkeypatch.delenv(TOKEN_FILE_ENV, raising=False)
    with pytest.raises(TokenError):
        settings_class.from_env()
