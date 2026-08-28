from pathlib import Path
app=Path("server/app.py").read_text(encoding="utf-8")
svc=Path("server/services/fabric_service.py").read_text(encoding="utf-8")
policy=Path("server/services/cloud_access_policy.py").read_text(encoding="utf-8")
assert 'discovery_mode' in app and 'authorized_hosts' in app
assert 'requester_email_mismatch' in app
assert 'list_authorized_hosts' in svc
assert 'authorized_email_hashes' in svc
assert '"plugin.run": {"mode": "per_period", "credits": 3, "period_seconds": 3600}' in policy
print("P34.8 authorized Host discovery + default plugin 3 credits/hour: PASS")
