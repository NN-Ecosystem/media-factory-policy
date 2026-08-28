from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
fabric=(ROOT/"server/services/fabric_service.py").read_text(encoding="utf-8")
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
for n in ["public_host_id: str","_public_hosts","relay_token_for_public_host"]:
    assert n in fabric, n
for n in [
    '/v1/cloud/host/{public_host_id}/',
    "HOST_OFFLINE",
    "public_base_path",
    'item.pop("relay_token", None)',
    '"public_host_id": row.public_host_id',
]:
    assert n in app, n
assert 'remote_url = f"{base}/v1/cloud/host/{row.public_host_id}/"' in app
print("CLOUD 3.4.1G STABLE HOST URL: PASS")
