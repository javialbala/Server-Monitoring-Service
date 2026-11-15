import pytest

from minipaas.common.secrets import TOKEN_FILE_ENV, TokenError, read_token, read_token_from_env

VALID = "a" * 40


def test_missing_file(tmp_path):
    with pytest.raises(TokenError, match="No existe"):
        read_token(tmp_path / "nope")


def test_too_short(tmp_path):
    file = tmp_path / "token"
    file.write_text("corto")
    with pytest.raises(TokenError, match="demasiado corto"):
        read_token(file)


def test_strips_trailing_newline(tmp_path):
    file = tmp_path / "token"
    file.write_text(VALID + "\n")
    assert read_token(file) == VALID


def test_valid(tmp_path):
    file = tmp_path / "token"
    file.write_text(VALID)
    assert read_token(file) == VALID


def test_unreadable_path_is_token_error(tmp_path):
    # Un directorio no se puede leer como archivo.
    with pytest.raises(TokenError):
        read_token(tmp_path)


def test_env_variable_missing(monkeypatch):
    monkeypatch.delenv(TOKEN_FILE_ENV, raising=False)
    with pytest.raises(TokenError, match=TOKEN_FILE_ENV):
        read_token_from_env()


def test_env_variable_points_to_file(monkeypatch, tmp_path):
    file = tmp_path / "token"
    file.write_text(VALID)
    monkeypatch.setenv(TOKEN_FILE_ENV, str(file))
    assert read_token_from_env() == VALID
