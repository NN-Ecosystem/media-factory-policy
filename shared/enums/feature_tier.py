from enum import IntEnum


class FeatureTier(IntEnum):
    """
    Hierarchy of feature permissions across ecosystem
    """

    FREE = 0
    BASIC = 1
    PRO = 2
    ENTERPRISE = 3

    # -----------------------------
    # COMPARISON SUPPORT
    # -----------------------------
    def __ge__(self, other):
        if isinstance(other, FeatureTier):
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, FeatureTier):
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, FeatureTier):
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, FeatureTier):
            return self.value < other.value
        return NotImplemented