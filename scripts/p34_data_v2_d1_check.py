from pathlib import Path
R=Path(__file__).resolve().parents[1]
layout=(R/"server/data_layout_v2.py").read_text(encoding="utf-8")
app=(R/"server/app.py").read_text(encoding="utf-8")
inv=(R/"server/services/data_migration_inventory.py").read_text(encoding="utf-8")
for x in ["cloud_users","core_wallets","credit_orders","plan_policies","audit_events","store_comments"]:
    assert x in layout
for x in ["/v1/cloud/admin/data-v2/summary","/v1/cloud/admin/data-v2/retention","/v1/cloud/admin/data-v2/migration/dry-run"]:
    assert x in app
assert '"destructive_changes":False' in inv
assert '"write_mode":"NONE"' in app
print("CLOUD DATA V2 D1 FOUNDATION: PASS")
