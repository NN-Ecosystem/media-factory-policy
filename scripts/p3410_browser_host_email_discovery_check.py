from pathlib import Path
app=Path("server/app.py").read_text(encoding="utf-8")
svc=Path("server/services/fabric_service.py").read_text(encoding="utf-8")
policy=Path("server/services/cloud_access_policy.py").read_text(encoding="utf-8")
assert '@app.get("/v1/cloud/connect"' in app
assert '@app.post("/v1/cloud/host/resolve")' in app
assert 'public_host_for_owner_email' in svc
assert 'owner_email_hash' in svc
assert 'HOST_NOT_AVAILABLE' in app
assert '"plugin.run": {"mode": "per_period", "credits": 3, "period_seconds": 3600}' in policy
print("P34.10 browser Host-email discovery + plugin 3 credits/hour: PASS")
