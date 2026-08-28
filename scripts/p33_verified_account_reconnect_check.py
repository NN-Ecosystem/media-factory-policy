"""Static guard: verified email activation must support Trial + paid entitlement reconnect."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = (root / "server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
start = src.index("def activate_licensed_account_by_email")
end = src.index("def activate_linked_license_account", start)
body = src[start:end]

assert "Trial-only/new email is NOT accepted" not in body
assert 'source_type") or "") == "trial"' not in body
assert "_select_core_entitlement" in body
assert "_reserve_activation" in body
assert "_recover_same_device_core" in body
print("P33 VERIFIED ACCOUNT TRIAL/PAID RECONNECT: PASSED")
