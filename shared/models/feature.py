from dataclasses import dataclass, field
from typing import List, Dict, Optional

from shared.enums.feature_tier import FeatureTier


@dataclass
class Feature:
    """
    Core permission unit across ecosystem_verify system
    """

    name: str
    tier: FeatureTier = FeatureTier.FREE

    capabilities: List[str] = field(default_factory=list)

    limits: Dict[str, int] = field(default_factory=dict)

    description: Optional[str] = None

    # -----------------------------
    # TIER CHECK
    # -----------------------------
    def has_tier(self, required: FeatureTier) -> bool:
        """
        Check if current feature tier satisfies required tier
        """

        # SAFE guard (avoid None or invalid enum crash)
        if not self.tier or not required:
            return False

        return self.tier.value >= required.value

    # -----------------------------
    # CAPABILITY CHECK
    # -----------------------------
    def can(self, capability: str) -> bool:
        """
        Check feature capability access
        """

        if not capability:
            return False

        return capability in self.capabilities

    # -----------------------------
    # LIMIT ACCESS
    # -----------------------------
    def get_limit(self, key: str) -> Optional[int]:
        """
        Get quota limit (future scaling system)
        """

        return self.limits.get(key)

    # -----------------------------
    # FEATURE VALIDITY
    # -----------------------------
    def is_available(self) -> bool:
        """
        Check if feature is valid for runtime use
        """

        return self.tier is not None and isinstance(self.capabilities, list)