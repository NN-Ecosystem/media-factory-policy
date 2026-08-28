from pathlib import Path
R=Path(__file__).resolve().parents[1]
bridge=(R/"server/repositories/data_v2_bridge.py").read_text(encoding="utf-8")
assert "v2_compat" in bridge and "legacy_shadow_write" in bridge
for rel, needles in {
 "server/repositories/wallet_repository.py":["wallet_ref_for_user","DataV2Bridge"],
 "server/repositories/credit_order_repository.py":["ref_for_user","DataV2Bridge"],
 "server/repositories/plan_policy_repository.py":["system","DataV2Bridge"],
 "server/repositories/owner_repository.py":["system_doc","DataV2Bridge"],
}.items():
    s=(R/rel).read_text(encoding="utf-8")
    for n in needles: assert n in s,(rel,n)
print("CLOUD DATA V2 D3 REPOSITORY SWITCH: PASS")
