from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; s=(ROOT/'server/services/cloud_access_policy.py').read_text(encoding='utf-8')
assert '"pipeline.run": {"mode": "per_run", "credits": 1}' in s
assert '"plugin.run": {"mode": "per_period", "credits": 3, "period_seconds": 3600}' in s
assert '"node.run": {"mode": "per_period", "credits": 7, "period_seconds": 3600}' in s
assert '"trial_grant_credits": 200' in s and '"quota_class":"unlimited"' in s
print('P34.4C1 SIMPLE CREDIT POLICY: PASS')
