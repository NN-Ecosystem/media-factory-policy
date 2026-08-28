from pathlib import Path
R=Path(__file__).resolve().parents[1]
for rel,needles in {
"server/repositories/onboarding_session_repository.py":["operations_collection","DataV2Bridge"],
"server/repositories/email_verification_repository.py":["operations_collection","DataV2Bridge"],
"server/repositories/audit_repository.py":["operations_collection","DataV2Bridge"],
"server/repositories/store_comment_repository.py":["community_collection","DataV2Bridge"],
}.items():
    s=(R/rel).read_text(encoding="utf-8")
    for n in needles: assert n in s,(rel,n)
a=(R/"server/app.py").read_text(encoding="utf-8")
for n in ["/v1/cloud/admin/data-v2/retention/run","/v1/cloud/admin/data-v2/cleanup-switched-legacy"]:
    assert n in a,n
r=(R/"server/services/data_v2_retention_service.py").read_text(encoding="utf-8")
assert "cleanup_switched_legacy" in r
print("CLOUD DATA V2 D4A OPERATIONS: PASS")
