import sqlite3

import pytest

from minipaas.controlplane.repositories import applications as apps
from minipaas.controlplane.repositories import users

NOW = "2030-01-01T00:00:00+00:00"


def test_users_roundtrip_and_case_insensitive_lookup(conn):
    assert users.count(conn) == 0
    created = users.create(conn, "Admin", "hash", NOW)
    assert users.get_by_username(conn, "ADMIN") == created
    assert users.get_by_id(conn, created.id) == created
    assert users.get_by_username(conn, "otro") is None
    assert users.count(conn) == 1


def test_applications_crud_and_order(conn):
    first = apps.create(conn, "primera", "Primera", "", "2030-01-01T00:00:00+00:00")
    apps.create(conn, "segunda", "Segunda", "d", "2030-01-02T00:00:00+00:00")
    assert [a.slug for a in apps.list_all(conn)] == ["segunda", "primera"]
    assert first.status == "draft" and first.status_label == "Sin desplegar"
    changed = apps.update(conn, "primera", "Nueva", "desc", "2030-02-01T00:00:00+00:00")
    assert (changed.name, changed.description) == ("Nueva", "desc")
    assert apps.delete(conn, "primera") is True
    assert apps.delete(conn, "primera") is False
    assert apps.get_by_slug(conn, "primera") is None


def test_duplicate_slug_raises_integrity_error(conn):
    apps.create(conn, "repetida", "A", "", NOW)
    with pytest.raises(sqlite3.IntegrityError):
        apps.create(conn, "repetida", "B", "", NOW)
