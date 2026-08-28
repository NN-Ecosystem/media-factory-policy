from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
fabric=(ROOT/"server/services/fabric_service.py").read_text(encoding="utf-8")
assert '@app.websocket("/v1/cloud/fabric/connect")' in app
assert '@app.post("/v1/cloud/fabric/hosts")' in app
assert '/v1/cloud/fabric/relay/{relay_token}/' in app
assert "FABRIC_RELAY_PATH_DENIED" in app
assert "relay_token" in fabric
assert "async def relay_request(" in fabric
assert "async def accept_relay_response(" in fabric
print("CLOUD 3.4.1 FABRIC RELAY: PASS")
