# P35.7
- Restores POST /v1/cloud/cores/deactivate.
- Restores Cloud self-deactivation service/registration lifecycle support.
- Heartbeat returns seat_active_count + seat_limit.
- Core stores those counts in a local display-only sidecar, never mutating the signed grant.
- Effective Access overlays seat counts only when current user_id/core_id match.
- Authoritative revoke clears both grant and seat overlay.
