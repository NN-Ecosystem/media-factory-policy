from dataclasses import dataclass, field
from typing import List, Optional
import time


@dataclass
class User:
    """
    Core user entity for ecosystem_verify
    """

    user_id: str
    email: str

    name: Optional[str] = None

    # subscription / plan overview
    plan: str = "free"

    # list of license keys owned
    licenses: List[str] = field(default_factory=list)

    # metadata
    is_active: bool = True

    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    # -----------------------------
    # BASIC HELPERS
    # -----------------------------
    def add_license(self, license_key: str):
        if license_key not in self.licenses:
            self.licenses.append(license_key)
            self.updated_at = int(time.time())

    def remove_license(self, license_key: str):
        if license_key in self.licenses:
            self.licenses.remove(license_key)
            self.updated_at = int(time.time())

    def has_license(self, license_key: str) -> bool:
        return license_key in self.licenses

    # -----------------------------
    # STATUS CHECK
    # -----------------------------
    def deactivate(self):
        self.is_active = False
        self.updated_at = int(time.time())

    def activate(self):
        self.is_active = True
        self.updated_at = int(time.time())