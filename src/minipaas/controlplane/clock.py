"""Reloj inyectable: permite probar caducidades sin esperar de verdad."""

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """Formato de fecha de toda la base de datos: ISO 8601 UTC con segundos."""
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def from_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)
