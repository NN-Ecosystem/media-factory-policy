from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/"server/services/credit_order_service.py").read_text(encoding="utf-8")
expected=[
    ('CORE_CREDIT_200',200,500),
    ('CORE_CREDIT_500',500,1000),
    ('CORE_CREDIT_1200',1200,2000),
    ('CORE_CREDIT_3500',3500,5000),
    ('CORE_CREDIT_8000',8000,10000),
]
for package_id,credits,price_minor in expected:
    assert f'"package_id": "{package_id}"' in s
    row=next(line for line in s.splitlines() if f'"package_id": "{package_id}"' in line)
    assert f'"credits": {credits}' in row, row
    assert f'"price_minor": {price_minor}' in row, row
p=(ROOT/"server/services/cloud_access_policy.py").read_text(encoding="utf-8")
assert '"trial_grant_credits": 200' in p
assert 'CLOUD_TRIAL_CREDITS", "200"' in p
print("CLOUD P34.8 CREDIT VALUE REFRESH: PASS")
