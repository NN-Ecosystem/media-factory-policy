from pathlib import Path
root=Path(__file__).resolve().parents[1]
foundation=(root/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
policy=(root/"server/services/cloud_access_policy.py").read_text(encoding="utf-8")
block=foundation[foundation.index('if purpose == "trial_verification"'):foundation.index('else:', foundation.index('if purpose == "trial_verification"'))]
assert "seat_limit=1" in block
assert '"transfer": "admin_only"' in block
assert policy.count('"quota_scope": "entitlement_activation_local_day"') >= 2
assert policy.count('"trial_seat_limit": 1') >= 2
print("P33 TRIAL SEAT / QUOTA SCOPE: PASSED")
