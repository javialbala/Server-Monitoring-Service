import pytest

from minipaas.controlplane.security import passwords


def test_hash_is_argon2id_and_verifies():
    password_hash = passwords.hash_password("una-contraseña-larga")
    assert password_hash.startswith("$argon2id$")
    assert passwords.verify_password(password_hash, "una-contraseña-larga")
    assert not passwords.verify_password(password_hash, "otra-contraseña")


def test_verify_with_garbage_hash_is_false():
    assert passwords.verify_password("esto-no-es-un-hash", "x") is False


def test_dummy_hash_never_matches():
    assert not passwords.verify_password(passwords.DUMMY_HASH, "cualquier-cosa")


def test_fresh_hash_does_not_need_rehash():
    assert not passwords.needs_rehash(passwords.hash_password("una-contraseña-larga"))


def test_weak_hash_needs_rehash():
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("x" * 12)
    assert passwords.needs_rehash(weak)


@pytest.mark.parametrize("password", ["corta", "x" * 11, "x" * 129])
def test_invalid_length(password):
    with pytest.raises(passwords.WeakPassword):
        passwords.validate_new_password(password)


@pytest.mark.parametrize("password", ["x" * 12, "x" * 128])
def test_valid_length(password):
    passwords.validate_new_password(password)
