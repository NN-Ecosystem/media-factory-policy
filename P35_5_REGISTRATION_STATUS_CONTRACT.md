# P35.5 — Cloud Registration Status Contract

Heartbeat Cloud responses are now explicit:
- CORE_REGISTRATION_NOT_FOUND -> reconciliation; cached grant may be preserved temporarily.
- CORE_CREDENTIAL_INVALID -> reconciliation; cached grant may be preserved temporarily.
- CORE_REPLACED -> authoritative denial; clear cached signed grant.
- CORE_DEACTIVATED -> authoritative denial; clear cached signed grant.
- CORE_ACCOUNT_MISMATCH -> authoritative denial; clear cached signed grant.
- SEAT_REVOKED / SEAT_GENERATION_STALE / PLAN_POLICY_DISABLED remain authoritative denials.

Compatibility:
- CORE_REGISTRATION_INVALID remains reconciliation-only for older Cloud builds.

Streamlit fragment warning:
- The P35.4 changed-file Core package does not contain the UI fragment implementation,
  so no speculative UI patch is included here. Patch that separately from the current full Core source.
