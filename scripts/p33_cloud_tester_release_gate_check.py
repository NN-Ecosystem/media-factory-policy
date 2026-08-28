"""Cloud Factory 3.3 Tester Release Gate — static, stdlib-only."""
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]
app=(root/"server/app.py").read_text(encoding="utf-8")
foundation=(root/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
policy=(root/"server/services/cloud_access_policy.py").read_text(encoding="utf-8")

route_pairs=re.findall(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)',app)
assert len(route_pairs)==len(set(route_pairs)), "Duplicate FastAPI method/path route"
routes=[path for _method,path in route_pairs]
for route in (
    "/v1/cloud/access-grants",
    "/v1/cloud/admin/accounts/cleanup-preview",
    "/v1/cloud/admin/accounts/cleanup",
    "/v1/cloud/admin/maintenance/orphans/scan",
    "/v1/cloud/admin/maintenance/orphans/cleanup",
    "/v1/cloud/admin/maintenance/transients/scan",
    "/v1/cloud/admin/maintenance/transients/cleanup",
):
    assert route in routes, f"Missing route: {route}"

start=foundation.index("def activate_licensed_account_by_email")
end=foundation.index("def activate_linked_license_account",start)
direct=foundation[start:end]
assert "Trial-only/new email is NOT accepted" not in direct
assert 'source_type") or "") == "trial"' not in direct
assert "_select_core_entitlement" in direct
assert "self.issue_grant" in direct, "Email refresh must converge through canonical issue_grant path"
assert "CORE_CREDENTIAL_INVALID" in direct

verify_start=foundation.index('if purpose == "trial_verification"')
verify_end=foundation.index("else:",verify_start)
verify=foundation[verify_start:verify_end]
assert "seat_limit=1" in verify
assert '"transfer": "admin_only"' in verify
assert policy.count('"quota_scope": "entitlement_activation_local_day"') >= 2
assert policy.count('"trial_seat_limit": 1') >= 2

grant=foundation[foundation.index("def issue_grant"):foundation.index("def activate_licensed_account_by_email")]
# issue_grant owns grant/seat convergence errors. Email/onboarding-specific
# registration errors live in their respective entry points and should not be
# forced back into issue_grant merely to satisfy a historical source-string test.
for marker in (
    "ACCOUNT_NOT_ACTIVE","CORE_CREDENTIAL_INVALID",
    "ENTITLEMENT_INACTIVE","ACTIVATION_OWNERSHIP_CONFLICT",
):
    assert marker in grant
for marker in ("CORE_REGISTRATION_INVALID", "ACTIVATION_ENTITLEMENT_INACTIVE"):
    assert marker in foundation

for p in (root/"server").rglob("*.py"):
    text=p.read_text(encoding="utf-8")
    assert not re.search(r'\.where\(\s*["\'][^"\']+["\']\s*,\s*["\']',text), f"Positional Firestore .where: {p}"

print("P33 CLOUD TESTER RELEASE GATE: PASSED")
