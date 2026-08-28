from enum import Enum


class VerifyStatus(Enum):
    """
    Result states for license verification pipeline
    """

    # -------------------------
    # SUCCESS
    # -------------------------
    VALID = "valid"

    # -------------------------
    # GENERAL
    # -------------------------
    INVALID = "invalid"

    SERVER_ERROR = "server_error"

    OFFLINE = "offline"

    # -------------------------
    # LICENSE
    # -------------------------
    NOT_FOUND = "not_found"

    EXPIRED = "expired"

    REVOKED = "revoked"

    # -------------------------
    # MACHINE
    # -------------------------
    MACHINE_MISMATCH = "machine_mismatch"

    MACHINE_LIMIT = "machine_limit"

    # -------------------------
    # FEATURE
    # -------------------------
    FEATURE_REVOKED = "feature_revoked"