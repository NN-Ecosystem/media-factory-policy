from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/"server/services/data_v2_migration_service.py").read_text(encoding="utf-8")
app=(R/"server/app.py").read_text(encoding="utf-8")
for x in ["migrate_system","migrate_accounts","migrate_economy","migrate_operations","wallet_invariants_match","V2_REPOSITORY_SWITCH_REQUIRED"]:
    assert x in s,x
for x in ["/migration/system","/migration/accounts","/migration/economy","/migration/operations","/migration/verify","/migration/status","/migration/cleanup-legacy"]:
    assert x in app,x
print("CLOUD DATA V2 D2 MIGRATION: PASS")
