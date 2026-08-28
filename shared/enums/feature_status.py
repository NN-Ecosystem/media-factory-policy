from enum import Enum


class FeatureStatus(str, Enum):

    ACTIVE = "active"

    TRIAL = "trial"

    PENDING = "pending"

    EXPIRED = "expired"

    DISABLED = "disabled"

    REVOKED = "revoked"

    @property
    def usable(self) -> bool:
        return self in (
            FeatureStatus.ACTIVE,
            FeatureStatus.TRIAL,
        )

    @property
    def blocked(self) -> bool:
        return self in (
            FeatureStatus.EXPIRED,
            FeatureStatus.DISABLED,
            FeatureStatus.REVOKED,
        )