from minipaas.controlplane.repositories import sessions as sessions_repo
from minipaas.controlplane.repositories import users as users_repo
from minipaas.controlplane.security.sessions import SessionService, hash_token


def setup(conn, clock):
    user = users_repo.create(conn, "alice", "hash", "2030-01-01T12:00:00+00:00")
    return user, SessionService(idle_minutes=30, absolute_hours=8, clock=clock)


def test_create_stores_only_the_hash(conn, clock):
    user, service = setup(conn, clock)
    raw, session = service.create(conn, user.id)
    assert session.token_hash == hash_token(raw) != raw
    stored = conn.execute("SELECT * FROM sessions").fetchone()
    assert raw not in tuple(stored)
    assert len(raw) >= 43  # 32 bytes en base64 url-safe


def test_tokens_are_unique(conn, clock):
    user, service = setup(conn, clock)
    assert service.create(conn, user.id)[0] != service.create(conn, user.id)[0]


def test_resolve_valid_unknown_and_revoked(conn, clock):
    user, service = setup(conn, clock)
    raw, session = service.create(conn, user.id)
    assert service.resolve(conn, raw).id == session.id
    assert service.resolve(conn, "desconocido") is None
    service.revoke(conn, session.id)
    assert service.resolve(conn, raw) is None


def test_idle_expiry(conn, clock):
    user, service = setup(conn, clock)
    raw, _ = service.create(conn, user.id)
    clock.advance(minutes=30)
    assert service.resolve(conn, raw) is not None  # justo en el límite sigue valiendo
    clock.advance(minutes=30, seconds=1)
    assert service.resolve(conn, raw) is None


def test_absolute_expiry_even_if_active(conn, clock):
    user, service = setup(conn, clock)
    raw, _ = service.create(conn, user.id)
    for _ in range(16):  # actividad cada 29 minutos (7 h 44 min)
        clock.advance(minutes=29)
        assert service.resolve(conn, raw) is not None
    clock.advance(minutes=29)  # 8 h 13 min: pasó la caducidad absoluta
    assert service.resolve(conn, raw) is None


def test_last_seen_is_only_updated_after_60_seconds(conn, clock):
    user, service = setup(conn, clock)
    raw, session = service.create(conn, user.id)
    clock.advance(seconds=30)
    service.resolve(conn, raw)
    assert (
        sessions_repo.get_by_token_hash(conn, session.token_hash).last_seen_at == session.created_at
    )
    clock.advance(seconds=31)
    service.resolve(conn, raw)
    assert (
        sessions_repo.get_by_token_hash(conn, session.token_hash).last_seen_at != session.created_at
    )


def test_revoke_all_for_user(conn, clock):
    user, service = setup(conn, clock)
    tokens = [service.create(conn, user.id)[0] for _ in range(3)]
    service.revoke_all_for_user(conn, user.id)
    assert all(service.resolve(conn, token) is None for token in tokens)


def test_purge_expired_and_old_revoked(conn, clock):
    user, service = setup(conn, clock)
    _, old = service.create(conn, user.id)
    _, revoked = service.create(conn, user.id)
    service.revoke(conn, revoked.id)
    clock.advance(days=2)
    _, fresh = service.create(conn, user.id)
    assert service.purge_expired(conn) == 2
    remaining = [r["id"] for r in conn.execute("SELECT id FROM sessions")]
    assert remaining == [fresh.id] and old.id not in remaining
