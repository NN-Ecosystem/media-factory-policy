from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
assert "local_pathname" in app
assert "_relay_path_allowed(local_pathname)" in app
assert "__CORE_FACTORY_RELAY_BASE__" in app
assert "json.dumps(relay_base)" in app
print("CLOUD 3.4.1A RELAY HTML/QUERY: PASS")
