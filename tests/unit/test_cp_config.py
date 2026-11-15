import pytest

from minipaas.common.secrets import TOKEN_FILE_ENV
from minipaas.controlplane.config import ConfigError, ControlPlaneSettings


def test_test_catalog_is_disabled_by_default(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/x")
    monkeypatch.delenv("MINIPAAS_ENABLE_TEST_CATALOG", raising=False)
    assert ControlPlaneSettings.from_env().enable_test_catalog is False


def test_test_catalog_flag(monkeypatch):
    monkeypatch.setenv(TOKEN_FILE_ENV, "/x")
    monkeypatch.setenv("MINIPAAS_ENABLE_TEST_CATALOG", "true")
    assert ControlPlaneSettings.from_env().enable_test_catalog is True
    monkeypatch.setenv("MINIPAAS_ENABLE_TEST_CATALOG", "quizá")
    with pytest.raises(ConfigError):
        ControlPlaneSettings.from_env()
