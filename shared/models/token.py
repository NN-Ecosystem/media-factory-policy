from dataclasses import dataclass, field
from typing import Dict, Any

from shared.models.feature import Feature


@dataclass
class LicenseToken:
    """
    Core license unit across ecosystem
    """

    user_id: str
    machine_id: str

    # unix timestamp
    expire_at: int

    # feature map: feature_name -> Feature
    features: Dict[str, Feature] = field(default_factory=dict)

    # optional metadata
    plan: str = "free"

    # versioning for future upgrades (RSA, quota, etc.)
    version: str = "v1"

    def is_expired(self, current_time: int) -> bool:
        return current_time > self.expire_at

    def has_feature(self, feature_name: str) -> bool:
        return feature_name in self.features

    def get_feature(self, feature_name: str) -> Feature | None:
        return self.features.get(feature_name)

    def can(self, feature_name: str, capability: str = None) -> bool:
        """
        Unified feature access check
        """
        feature = self.get_feature(feature_name)

        if not feature:
            return False

        if capability:
            return feature.can(capability)

        return True

    def tier(self, feature_name: str):
        feature = self.get_feature(feature_name)
        return feature.tier if feature else None