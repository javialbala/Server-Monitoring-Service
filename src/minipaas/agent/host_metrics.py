"""Métricas del anfitrión leídas de /proc, /sys, os-release y statvfs (solo lectura).

Las rutas son parámetros para poder probar las funciones con directorios falsos.
Dentro de un contenedor, /proc/stat, /proc/meminfo y /proc/uptime muestran los
valores del anfitrión, así que no hace falta montarlos.
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path


def read_hostname(hostfs: str = "/") -> str | None:
    try:
        return (Path(hostfs) / "etc/hostname").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def read_os_name(hostfs: str = "/") -> str | None:
    """PRETTY_NAME de os-release (en /etc o, si no, en /usr/lib)."""
    for relative in ("etc/os-release", "usr/lib/os-release"):
        try:
            text = (Path(hostfs) / relative).read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"') or None
    return None


def read_uptime_seconds(proc: str = "/proc") -> int | None:
    try:
        return int(float((Path(proc) / "uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def _read_cpu_times(proc: str) -> tuple[int, int]:
    """Devuelve (idle, total) de la línea `cpu` de /proc/stat."""
    first_line = (Path(proc) / "stat").read_text().splitlines()[0]
    values = [int(v) for v in first_line.split()[1:]]
    idle = values[3] + values[4]  # idle + iowait
    return idle, sum(values)


def read_cpu_percent(proc: str = "/proc", interval: float = 0.5) -> float:
    """Uso de CPU medido con dos lecturas de /proc/stat separadas `interval` segundos."""
    idle_1, total_1 = _read_cpu_times(proc)
    time.sleep(interval)
    idle_2, total_2 = _read_cpu_times(proc)
    total_delta = total_2 - total_1
    if total_delta <= 0:
        return 0.0
    return round(100 * (1 - (idle_2 - idle_1) / total_delta), 1)


def read_cpu_model(proc: str = "/proc") -> str | None:
    """Modelo de CPU; None si /proc/cpuinfo no tiene "model name" (p. ej. en ARM)."""
    try:
        for line in (Path(proc) / "cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip() or None
    except OSError:
        pass
    return None


def read_memory(proc: str = "/proc") -> dict:
    values = {}
    for line in (Path(proc) / "meminfo").read_text().splitlines():
        name, _, rest = line.partition(":")
        values[name] = int(rest.split()[0]) * 1024  # /proc/meminfo está en kB
    total = values["MemTotal"]
    available = values["MemAvailable"]
    used = total - available
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "percent": round(used / total * 100, 1) if total else 0.0,
    }


def read_disk(hostfs: str = "/") -> dict:
    """Uso del disco del anfitrión; el porcentaje se calcula como lo hace `df`."""
    stats = os.statvfs(hostfs)
    total = stats.f_blocks * stats.f_frsize
    free = stats.f_bavail * stats.f_frsize
    used = (stats.f_blocks - stats.f_bfree) * stats.f_frsize
    percent = round(used / (used + free) * 100, 1) if used + free else 0.0
    return {
        "path": "/",
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "percent": percent,
    }


def read_temperatures(sys_root: str = "/sys") -> list[dict]:
    """Sensores de /sys/class/thermal (la temperatura viene en milésimas de grado)."""
    sensors = []
    for zone in sorted(Path(sys_root, "class/thermal").glob("thermal_zone*")):
        try:
            name = (zone / "type").read_text().strip()
            celsius = round(int((zone / "temp").read_text()) / 1000, 1)
        except (OSError, ValueError):
            continue  # sensor ilegible: se ignora
        sensors.append({"sensor": name, "celsius": celsius})
    return sensors


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_metrics(hostfs: str = "/", proc: str = "/proc", sys_root: str = "/sys") -> dict:
    uname = os.uname()
    return {
        "collected_at": now_iso(),
        "hostname": read_hostname(hostfs),
        "os": {
            "name": read_os_name(hostfs),
            "kernel": uname.release,  # el kernel es el mismo que el del anfitrión
            "architecture": uname.machine,
        },
        "uptime_seconds": read_uptime_seconds(proc),
        "cpu": {
            "percent": read_cpu_percent(proc),
            "cores": os.cpu_count(),
            "model": read_cpu_model(proc),
        },
        "memory": read_memory(proc),
        "disk": read_disk(hostfs),
        "temperatures": read_temperatures(sys_root),
    }
