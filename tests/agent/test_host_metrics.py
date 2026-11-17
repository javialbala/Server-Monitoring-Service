import os

from server_monitor.agent import host_metrics


def write(base, relative, text):
    file = base / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)


def test_hostname_and_os_name(tmp_path):
    write(tmp_path, "etc/hostname", "servidor\n")
    write(tmp_path, "etc/os-release", 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\n')
    assert host_metrics.read_hostname(str(tmp_path)) == "servidor"
    assert host_metrics.read_os_name(str(tmp_path)) == "Ubuntu 24.04.1 LTS"


def test_os_name_falls_back_to_usr_lib_and_missing_files(tmp_path):
    assert host_metrics.read_hostname(str(tmp_path)) is None
    assert host_metrics.read_os_name(str(tmp_path)) is None
    write(tmp_path, "usr/lib/os-release", "PRETTY_NAME=Arch Linux\n")
    assert host_metrics.read_os_name(str(tmp_path)) == "Arch Linux"


def test_uptime(tmp_path):
    write(tmp_path, "uptime", "12345.67 99999.00\n")
    assert host_metrics.read_uptime_seconds(str(tmp_path)) == 12345
    assert host_metrics.read_uptime_seconds(str(tmp_path / "no-existe")) is None


def test_cpu_percent_from_two_readings(tmp_path, monkeypatch):
    # user nice system idle iowait ...
    write(tmp_path, "stat", "cpu 100 0 100 700 100 0 0 0\n")
    readings = iter(["cpu 200 0 200 750 150 0 0 0\n"])

    def fake_sleep(_seconds):
        write(tmp_path, "stat", next(readings))

    monkeypatch.setattr(host_metrics.time, "sleep", fake_sleep)
    # Δtotal = 1300-1000 = 300; Δidle = (750+150)-(700+100) = 100 -> 66,7 % de uso
    assert host_metrics.read_cpu_percent(str(tmp_path), interval=0) == 66.7


def test_cpu_percent_without_changes_is_zero(tmp_path, monkeypatch):
    write(tmp_path, "stat", "cpu 1 0 1 8 0 0 0 0\n")
    monkeypatch.setattr(host_metrics.time, "sleep", lambda _s: None)
    assert host_metrics.read_cpu_percent(str(tmp_path)) == 0.0


def test_cpu_model_present_and_absent(tmp_path):
    write(tmp_path, "cpuinfo", "processor : 0\nmodel name\t: Intel(R) Fake CPU\n")
    assert host_metrics.read_cpu_model(str(tmp_path)) == "Intel(R) Fake CPU"
    write(tmp_path, "cpuinfo", "processor : 0\nCPU part : 0xd08\n")  # como en ARM
    assert host_metrics.read_cpu_model(str(tmp_path)) is None


def test_memory(tmp_path):
    write(tmp_path, "meminfo", "MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 250 kB\n")
    memory = host_metrics.read_memory(str(tmp_path))
    assert memory == {
        "total_bytes": 1000 * 1024,
        "used_bytes": 750 * 1024,
        "available_bytes": 250 * 1024,
        "percent": 75.0,
    }


def test_disk_uses_statvfs(monkeypatch):
    fake = os.statvfs_result((4096, 4096, 1000, 400, 300, 0, 0, 0, 0, 255))
    monkeypatch.setattr(host_metrics.os, "statvfs", lambda _path: fake)
    disk = host_metrics.read_disk("/hostfs", "Sistema", "/")
    assert disk["name"] == "Sistema" and disk["path"] == "/"
    assert disk["total_bytes"] == 1000 * 4096
    assert disk["free_bytes"] == 300 * 4096
    assert disk["used_bytes"] == 600 * 4096
    assert disk["percent"] == 66.7  # 600 / (600 + 300), como df


def fake_device(monkeypatch, devices):
    """Simula el st_dev de los directorios (por nombre); el resto usa la llamada real."""

    class Stat:
        st_mode = 0o40755  # directorio

        def __init__(self, dev):
            self.st_dev = dev

    real_path_stat = host_metrics.Path.stat
    real_os_stat = os.stat

    def path_stat(self, **kwargs):
        return Stat(devices[self.name]) if self.name in devices else real_path_stat(self, **kwargs)

    def os_stat(path, *args, **kwargs):
        return Stat(devices["root"]) if path == "/hostfs" else real_os_stat(path, *args, **kwargs)

    monkeypatch.setattr(host_metrics.Path, "stat", path_stat)
    monkeypatch.setattr(host_metrics.os, "stat", os_stat)


def test_disks_root_plus_extra_sorted_and_same_device_skipped(tmp_path, monkeypatch):
    for name in ("zeta", "datos", "copia"):
        (tmp_path / "disks" / name).mkdir(parents=True)
    (tmp_path / "disks" / "fichero.txt").write_text("no es un disco")
    # root=1; "copia" está en el mismo sistema de archivos que el raíz; el resto, no.
    fake_device(monkeypatch, {"root": 1, "copia": 1, "datos": 2, "zeta": 3})
    fake = os.statvfs_result((4096, 4096, 1000, 400, 300, 0, 0, 0, 0, 255))
    monkeypatch.setattr(host_metrics.os, "statvfs", lambda _path: fake)

    disks = host_metrics.read_disks("/hostfs", str(tmp_path / "disks"))

    assert [(d["name"], d["path"]) for d in disks] == [
        ("Sistema", "/"),
        ("datos", "/disks/datos"),
        ("zeta", "/disks/zeta"),
    ]


def test_disks_without_disks_dir_only_root(tmp_path, monkeypatch):
    fake_device(monkeypatch, {"root": 1})
    fake = os.statvfs_result((4096, 4096, 1000, 400, 300, 0, 0, 0, 0, 255))
    monkeypatch.setattr(host_metrics.os, "statvfs", lambda _path: fake)
    disks = host_metrics.read_disks("/hostfs", str(tmp_path / "no-existe"))
    assert [d["name"] for d in disks] == ["Sistema"]


def hwmon(base, number, driver, sensors):
    """Crea /class/hwmon/hwmonN con `sensors` = {"temp1": (etiqueta o None, valor)}."""
    folder = f"class/hwmon/hwmon{number}"
    write(base, f"{folder}/name", driver + "\n")
    for temp, (label, value) in sensors.items():
        write(base, f"{folder}/{temp}_input", f"{value}\n")
        if label:
            write(base, f"{folder}/{temp}_label", label + "\n")


def test_temperature_coretemp_uses_package_not_cores(tmp_path):
    hwmon(
        tmp_path,
        0,
        "coretemp",
        {"temp1": ("Package id 0", 46000), "temp2": ("Core 0", 70000), "temp3": ("Core 1", 71000)},
    )
    assert host_metrics.read_temperature(str(tmp_path)) == {
        "celsius": 46.0,
        "sensor": "coretemp: Package id 0",
    }


def test_temperature_k10temp_tctl_and_without_labels(tmp_path):
    hwmon(tmp_path, 0, "k10temp", {"temp1": ("Tctl", 52500), "temp2": ("Tccd1", 40000)})
    assert host_metrics.read_temperature(str(tmp_path)) == {
        "celsius": 52.5,
        "sensor": "k10temp: Tctl",
    }
    other = tmp_path / "otro"
    hwmon(other, 0, "k10temp", {"temp1": (None, 44000)})
    assert host_metrics.read_temperature(str(other))["celsius"] == 44.0


def test_temperature_falls_back_to_x86_pkg_temp(tmp_path):
    hwmon(tmp_path, 0, "nvme", {"temp1": ("Composite", 30000)})  # no es de la CPU: se ignora
    write(tmp_path, "class/thermal/thermal_zone0/type", "acpitz\n")
    write(tmp_path, "class/thermal/thermal_zone0/temp", "99000\n")
    write(tmp_path, "class/thermal/thermal_zone1/type", "x86_pkg_temp\n")
    write(tmp_path, "class/thermal/thermal_zone1/temp", "45000\n")
    assert host_metrics.read_temperature(str(tmp_path)) == {
        "celsius": 45.0,
        "sensor": "x86_pkg_temp",
    }


def test_temperature_none_without_sensors(tmp_path):
    assert host_metrics.read_temperature(str(tmp_path)) is None


def test_temperature_absurd_values_are_discarded(tmp_path):
    hwmon(tmp_path, 0, "coretemp", {"temp1": ("Package id 0", 200000)})  # 200 grados
    write(tmp_path, "class/thermal/thermal_zone0/type", "x86_pkg_temp\n")
    write(tmp_path, "class/thermal/thermal_zone0/temp", "0\n")
    assert host_metrics.read_temperature(str(tmp_path)) is None


NET_DEV = """Inter-|   Receive    |  Transmit
 face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs ...
    lo: 9999 10 0 0 0 0 0 0 9999 10 0 0 0 0 0 0
  eth0: 1000 10 0 0 0 0 0 0 400 5 0 0 0 0 0 0
wlan0:2000 20 0 0 0 0 0 0 600 8 0 0 0 0 0 0
veth1a2b: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0
br-abc123: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0
docker0: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0
virbr0: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0
"""


def test_network_sums_real_interfaces_and_excludes_virtual(tmp_path):
    write(tmp_path, "dev", NET_DEV)
    assert host_metrics.read_network(str(tmp_path / "dev")) == {
        "rx_bytes": 3000,
        "tx_bytes": 1000,
        "interfaces": [
            {"name": "eth0", "rx_bytes": 1000, "tx_bytes": 400},
            {"name": "wlan0", "rx_bytes": 2000, "tx_bytes": 600},
        ],
    }


def test_network_unreadable_file_is_none(tmp_path):
    assert host_metrics.read_network(str(tmp_path / "no-existe")) is None
    assert host_metrics.read_network(str(tmp_path)) is None  # un directorio, no un archivo
