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
    first_line = (Path(proc) / "stat").read_text().splitlines()[0]
    values = [int(v) for v in first_line.split()[1:]]
    idle = values[3] + values[4]  # idle + iowait
    return idle, sum(values)


def read_cpu_percent(proc: str = "/proc", interval: float = 0.5) -> float:
    idle_1, total_1 = _read_cpu_times(proc)
    time.sleep(interval)
    idle_2, total_2 = _read_cpu_times(proc)
    total_delta = total_2 - total_1
    if total_delta <= 0:
        return 0.0
    return round(100 * (1 - (idle_2 - idle_1) / total_delta), 1)


def read_cpu_model(proc: str = "/proc") -> str | None:
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


def read_disk(path: str, name: str, display_path: str) -> dict:
    """El porcentaje se calcula como lo hace `df`."""
    stats = os.statvfs(path)
    total = stats.f_blocks * stats.f_frsize
    free = stats.f_bavail * stats.f_frsize
    used = (stats.f_blocks - stats.f_bfree) * stats.f_frsize
    percent = round(used / (used + free) * 100, 1) if used + free else 0.0
    return {
        "name": name,
        "path": display_path,
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "percent": percent,
    }


def read_disks(hostfs: str = "/", disks_dir: str = "/disks") -> list[dict]:
    disks = [read_disk(hostfs, "Sistema", "/")]
    root_device = os.stat(hostfs).st_dev
    try:
        extras = sorted(p for p in Path(disks_dir).iterdir() if p.is_dir())
    except OSError:
        return disks  # no hay directorio de discos: solo el raíz
    for extra in extras:
        try:
            if extra.stat().st_dev == root_device:
                continue  # mismo sistema de archivos que el raíz: sería repetir el disco
            disks.append(read_disk(str(extra), extra.name, f"/disks/{extra.name}"))
        except OSError:
            continue  # disco ilegible: se ignora
    return disks


def _celsius_from_file(file: Path) -> float | None:
    try:
        celsius = int(file.read_text()) / 1000
    except (OSError, ValueError):
        return None
    return round(celsius, 1) if 0 < celsius <= 150 else None


def _read_hwmon_package(hwmon: Path) -> dict | None:
    try:
        driver = (hwmon / "name").read_text().strip()
    except OSError:
        return None
    wanted = {"coretemp": "Package id 0", "k10temp": "Tctl"}.get(driver)
    if wanted is None:
        return None
    candidates = []
    for label_file in sorted(hwmon.glob("temp*_label")):
        try:
            if label_file.read_text().strip() == wanted:
                candidates.append(hwmon / label_file.name.replace("_label", "_input"))
        except OSError:
            continue
    if driver == "k10temp" and not candidates:
        candidates = [hwmon / "temp1_input"]  # sin etiquetas: el primer sensor
    for candidate in candidates:
        celsius = _celsius_from_file(candidate)
        if celsius is not None:
            return {"celsius": celsius, "sensor": f"{driver}: {wanted}"}
    return None


def read_temperature(sys_root: str = "/sys") -> dict | None:
    for hwmon in sorted(Path(sys_root, "class/hwmon").glob("hwmon*")):
        found = _read_hwmon_package(hwmon)
        if found:
            return found
    for zone in sorted(Path(sys_root, "class/thermal").glob("thermal_zone*")):
        try:
            if (zone / "type").read_text().strip() != "x86_pkg_temp":
                continue
        except OSError:
            continue
        celsius = _celsius_from_file(zone / "temp")
        if celsius is not None:
            return {"celsius": celsius, "sensor": "x86_pkg_temp"}
    return None


IGNORED_INTERFACES = ("lo", "veth", "br-", "docker", "virbr")


def read_network(net_dev: str = "/proc/net/dev") -> dict | None:
    try:
        lines = Path(net_dev).read_text().splitlines()[2:]  # las 2 primeras son cabecera
    except OSError:
        return None
    interfaces = []
    for line in lines:
        name, _, counters = line.partition(":")
        name, fields = name.strip(), counters.split()
        if not name or len(fields) < 9 or name.startswith(IGNORED_INTERFACES):
            continue
        try:
            interfaces.append(
                {"name": name, "rx_bytes": int(fields[0]), "tx_bytes": int(fields[8])}
            )
        except ValueError:
            continue
    return {
        "rx_bytes": sum(i["rx_bytes"] for i in interfaces),
        "tx_bytes": sum(i["tx_bytes"] for i in interfaces),
        "interfaces": interfaces,
    }


def now_iso() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def collect_metrics(
    hostfs: str = "/",
    disks_dir: str = "/disks",
    net_dev: str = "/proc/net/dev",
    proc: str = "/proc",
    sys_root: str = "/sys",
) -> dict:
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
        "disks": read_disks(hostfs, disks_dir),
        "temperature": read_temperature(sys_root),
        "network": read_network(net_dev),
    }
