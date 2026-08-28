# shared/constants.py

# ==========================================================
# APPLICATION
# ==========================================================

APP_NAME = "ecosystem_verify"
APP_VERSION = "1.0.0"

TOKEN_VERSION = "1.0"


# ==========================================================
# CACHE FILES
# ==========================================================

LICENSE_CACHE_FILE = "license_cache.json"

MACHINE_FILE = "machine.json"

VERIFY_STATE_FILE = "verify_state.json"


# ==========================================================
# VERIFY
# ==========================================================

VERIFY_INTERVAL_HOURS = 24

OFFLINE_GRACE_DAYS = 7

DEFAULT_TOKEN_EXPIRE_DAYS = 30


# ==========================================================
# MACHINE
# ==========================================================

MAX_MACHINE_PER_LICENSE = 3


# ==========================================================
# LICENSE
# ==========================================================

DEFAULT_LICENSE_DAYS = 365


# ==========================================================
# FEATURE
# ==========================================================

DEFAULT_FEATURE_TIER = "basic"

DEFAULT_FEATURE_STATUS = "active"


# ==========================================================
# SECURITY
# ==========================================================

SIGNATURE_ALGORITHM = "HMAC-SHA256"

HASH_ALGORITHM = "SHA256"


# ==========================================================
# API
# ==========================================================

API_PREFIX = "/api"

VERIFY_ENDPOINT = "/verify"

FEATURE_ENDPOINT = "/features"

LICENSE_ENDPOINT = "/license"

STATUS_ENDPOINT = "/status"


# ==========================================================
# AGENT
# ==========================================================

AGENT_NAME = "ecosystem_agent"

AGENT_VERSION = "1.0.0"


# ==========================================================
# TOKEN KEYS
# ==========================================================

TOKEN_USER_ID = "user_id"

TOKEN_LICENSE_KEY = "license_key"

TOKEN_MACHINE_HASH = "machine_hash"

TOKEN_FEATURES = "features"

TOKEN_EXPIRES_AT = "expires_at"

TOKEN_ISSUED_AT = "issued_at"

TOKEN_SIGNATURE = "signature"