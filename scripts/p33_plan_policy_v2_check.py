from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=(root/"server/services/cloud_access_policy.py").read_text(encoding="utf-8")
f=(root/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
for x in ("trial", "basic", "pro", "master"): assert x in p
assert "Trial is capability-complete" in p
assert "usage_policy_projection" in p
assert 'payload["usage_policy"]' in f
assert "Manual account plan must be BASIC, PRO, or MASTER." in f
print("P33 CLOUD PLAN POLICY V2: PASSED")
