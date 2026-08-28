from dataclasses import dataclass, field
import hashlib
import platform
import uuid
import os


@dataclass
class MachineInfo:
    """
    Hardware fingerprint for ecosystem_verify
    """

    cpu: str
    disk: str
    mac: str
    hostname: str
    os: str

    machine_id: str = field(init=False)

    def __post_init__(self):
        self.machine_id = self.generate_machine_id()

    # -----------------------------
    # COLLECT SYSTEM INFO
    # -----------------------------
    @staticmethod
    def collect() -> "MachineInfo":
        """
        Gather lightweight hardware fingerprint (V1)
        """

        cpu = platform.processor()
        hostname = platform.node()
        os_name = platform.system()

        disk = MachineInfo.get_disk_id()
        mac = MachineInfo.get_mac_address()

        return MachineInfo(
            cpu=cpu,
            disk=disk,
            mac=mac,
            hostname=hostname,
            os=os_name
        )

    # -----------------------------
    # DISK ID (weak fingerprint)
    # -----------------------------
    @staticmethod
    def get_disk_id() -> str:
        try:
            return str(os.stat(".").st_dev)
        except Exception:
            return "unknown"

    # -----------------------------
    # MAC ADDRESS (normalized)
    # -----------------------------
    @staticmethod
    def get_mac_address() -> str:
        try:
            return hex(uuid.getnode())
        except Exception:
            return "unknown"

    # -----------------------------
    # MACHINE ID GENERATION
    # -----------------------------
    def generate_machine_id(self) -> str:
        """
        Stable fingerprint hash
        """

        raw = f"{self.cpu}|{self.disk}|{self.mac}|{self.hostname}|{self.os}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # -----------------------------
    # EXPORT
    # -----------------------------
    def to_dict(self) -> dict:
        return {
            "cpu": self.cpu,
            "disk": self.disk,
            "mac": self.mac,
            "hostname": self.hostname,
            "os": self.os,
            "machine_id": self.machine_id
        }