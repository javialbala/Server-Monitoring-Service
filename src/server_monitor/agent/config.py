import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    hostfs: str = "/"  # raíz del anfitrión (en el contenedor: /hostfs)
    disks_dir: str = "/disks"  # discos extra montados en solo lectura
    net_dev: str = "/proc/net/dev"  # en el contenedor: /host/net/dev

    @classmethod
    def from_env(cls) -> "AgentSettings":
        return cls(
            hostfs=os.environ.get("SMS_HOSTFS", cls.hostfs),
            disks_dir=os.environ.get("SMS_DISKS_DIR", cls.disks_dir),
            net_dev=os.environ.get("SMS_NET_DEV", cls.net_dev),
        )
