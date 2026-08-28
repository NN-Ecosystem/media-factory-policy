from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
app=(root/"server/app.py").read_text(encoding="utf-8")
models=(root/"server/models/cloud_models.py").read_text(encoding="utf-8")

assert '"/v1/cloud/admin/accounts/cleanup-preview"' in app
assert '"/v1/cloud/admin/accounts/cleanup"' in app
assert '"/v1/cloud/admin/maintenance/orphans/scan"' in app
assert '"/v1/cloud/admin/maintenance/orphans/cleanup"' in app
assert '"/v1/cloud/admin/maintenance/transients/scan"' in app
assert '"/v1/cloud/admin/maintenance/transients/cleanup"' in app
assert "CloudAdminOrphanCleanupRequest" in models or "CloudAdminOrphanCleanupRequest" in app

routes=re.findall(r'@app\.(?:get|post|put|delete|patch)\(\s*["\']([^"\']+)',app)
assert len(routes)==len(set(routes)), "duplicate FastAPI route detected"

for p in root.rglob("*.py"):
    if p.name.startswith("p33_"): continue
    s=p.read_text(encoding="utf-8")
    assert not re.search(r'\.where\(\s*["\'][^"\']+["\']\s*,\s*["\']',s), f"positional Firestore where: {p}"

print("P33 CLOUD TESTER CONSOLIDATION: PASSED")
