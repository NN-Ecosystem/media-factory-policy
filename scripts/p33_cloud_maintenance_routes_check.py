"""Static release guard for Cloud maintenance route completeness."""
from pathlib import Path

app = (Path(__file__).resolve().parents[1] / "server" / "app.py").read_text(encoding="utf-8")
required = (
    "/v1/cloud/admin/accounts/cleanup-preview",
    "/v1/cloud/admin/accounts/cleanup",
    "/v1/cloud/admin/maintenance/orphans/scan",
    "/v1/cloud/admin/maintenance/orphans/cleanup",
    "/v1/cloud/admin/maintenance/transients/scan",
    "/v1/cloud/admin/maintenance/transients/cleanup",
)
missing = [route for route in required if route not in app]
assert not missing, f"Missing Cloud maintenance routes: {missing}"
print("P33 CLOUD MAINTENANCE ROUTES: PASSED")
