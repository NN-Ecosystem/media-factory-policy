from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
svc=(ROOT/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
for route in ("/v1/cloud/usage/authorize","/v1/cloud/usage/capture","/v1/cloud/usage/release"):
    assert route in app, route
for method in ("def usage_authorize(","def usage_capture(","def usage_release("):
    assert method in svc, method
assert "resolve_usage_charge(" in svc
assert "wallet_service.reserve(" in svc
assert "wallet_service.capture(" in svc
assert "wallet_service.release(" in svc
print("P34.12 CLOUD USAGE ROUTES: PASS")
