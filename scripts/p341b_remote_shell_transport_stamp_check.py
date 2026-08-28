from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
assert "api_base_count = re.subn(" in app
assert 'f"const API_BASE={json.dumps(relay_base)};"' in app
assert "FABRIC_RELAY_STALE_OR_HOST_OFFLINE" in app
assert "status_code=410" in app
print("CLOUD 3.4.1B REMOTE SHELL TRANSPORT STAMP: PASS")
