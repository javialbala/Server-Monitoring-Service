import pytest

from minipaas.controlplane.services.applications import InvalidSlug, slugify, validate_slug


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Mi Aplicación Número 1", "mi-aplicacion-numero-1"),
        ("  Ñandú   &  Café  ", "nandu-cafe"),
        ("a" * 60, "a" * 40),
        ("Hola--mundo", "hola-mundo"),
        ("???", ""),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_slugify_trims_trailing_hyphen_after_cutting():
    assert slugify("a" * 39 + " bbb") == "a" * 39


@pytest.mark.parametrize("slug", ["abc", "mi-app", "app-2", "a1b", "a" * 40])
def test_valid_slugs(slug):
    assert validate_slug(slug) == slug


@pytest.mark.parametrize(
    "slug",
    ["", "ab", "Mi-App", "mi--app", "-app", "app-", "1app", "mi_app", "a" * 41, "mi app", "ñandú"],
)
def test_invalid_slugs(slug):
    with pytest.raises(InvalidSlug):
        validate_slug(slug)
