"""Current Cloud release gate. Historical Pxx checks remain archival regression probes."""
from pathlib import Path
import ast, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
if (ROOT/"server/server").exists(): errors.append("duplicate server/server package tree exists")
for p in (ROOT/"server").rglob("*.py"):
    try: ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
    except Exception as exc: errors.append(f"syntax: {p.relative_to(ROOT)}: {exc}")
checks=[
 "p33_cloud_tester_release_gate_check.py",
 "p33_cloud_grant_canonical_plan_import_check.py",
 "p33_cloud_maintenance_routes_check.py",
 "p33_trial_seat_quota_scope_check.py",
 "p34_trial_core_seat_transfer_check.py",
 "p34_2_wallet_ledger_check.py",
 "p34_3_usage_authorization_check.py",
 "p34_4_period_pricing_check.py",
 "p34_4c1_simple_credit_policy_check.py",
 "p34_5_credit_orders_check.py",
    "p34_6_seat_rank_check.py",
 "p35_plan_policy_signed_limits_check.py",
]
env=dict(__import__('os').environ); env['PYTHONPATH']=str(ROOT)
for name in checks:
    r=subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,env=env,text=True,capture_output=True)
    if r.returncode:
        errors.append(f"{name}: {(r.stderr or r.stdout).strip()}")
    else:
        print((r.stdout or '').strip())
if errors:
    print("[CLOUD-RELEASE-GATE] FAILED")
    for e in errors: print(" -",e)
    sys.exit(1)
print("[CLOUD-RELEASE-GATE] PASSED")
