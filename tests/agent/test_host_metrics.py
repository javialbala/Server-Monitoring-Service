import os

from minipaas.agent import host_metrics


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


def test_disk_uses_statvfs(tmp_path, monkeypatch):
    fake = os.statvfs_result((4096, 4096, 1000, 400, 300, 0, 0, 0, 0, 255))
    monkeypatch.setattr(host_metrics.os, "statvfs", lambda _path: fake)
    disk = host_metrics.read_disk("/hostfs")
    assert disk["total_bytes"] == 1000 * 4096
    assert disk["free_bytes"] == 300 * 4096
    assert disk["used_bytes"] == 600 * 4096
    assert disk["percent"] == 66.7  # 600 / (600 + 300), como df


def test_temperatures(tmp_path):
    write(tmp_path, "class/thermal/thermal_zone0/type", "x86_pkg_temp\n")
    write(tmp_path, "class/thermal/thermal_zone0/temp", "45000\n")
    write(tmp_path, "class/thermal/thermal_zone1/type", "roto\n")
    write(tmp_path, "class/thermal/thermal_zone1/temp", "no-es-numero\n")
    assert host_metrics.read_temperatures(str(tmp_path)) == [
        {"sensor": "x86_pkg_temp", "celsius": 45.0}
    ]


def test_temperatures_without_sensors(tmp_path):
    assert host_metrics.read_temperatures(str(tmp_path)) == []
