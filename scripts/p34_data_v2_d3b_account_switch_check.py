from pathlib import Path
R=Path(__file__).resolve().parents[1]
required={
"server/repositories/cloud_user_repository.py":["DataV2Bridge","identity_email"],
"server/repositories/core_repository.py":["identity_core","account_doc"],
"server/repositories/entitlement_repository.py":["identity_entitlement","account_root"],
"server/repositories/user_trial_repository.py":["DataV2Bridge","trials"],
"server/repositories/seat_upgrade_repository.py":["commerce_seat_order","access_projections","FieldFilter"],
}
for rel,needles in required.items():
 s=(R/rel).read_text(encoding="utf-8")
 for n in needles: assert n in s,(rel,n)
m=(R/"server/services/data_v2_migration_service.py").read_text(encoding="utf-8")
assert "def build_indexes" in m
a=(R/"server/app.py").read_text(encoding="utf-8")
assert "/v1/cloud/admin/data-v2/migration/indexes" in a
print("CLOUD DATA V2 D3B ACCOUNT SWITCH: PASS")
