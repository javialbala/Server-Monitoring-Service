import logging

import pytest
from conftest import PASSWORD
from fastapi.testclient import TestClient

from server_monitor.panel.main import build_app_from_env


@pytest.mark.parametrize("password", [None, "", "abc", "x" * 129])
def test_invalid_app_password_exits_without_logging_it(monkeypatch, caplog, password):
    if password is None:
        monkeypatch.delenv("APP_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("APP_PASSWORD", password)
    with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
        build_app_from_env()
    assert exit_info.value.code == 1
    assert "APP_PASSWORD" in caplog.text
    assert not password or password not in caplog.text


def test_login_uses_app_password(monkeypatch, caplog):
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)
    with caplog.at_level(logging.INFO), TestClient(build_app_from_env()) as client:
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
        assert client.post("/api/login", json={"password": "otra"}).status_code == 401
    assert PASSWORD not in caplog.text
