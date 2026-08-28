from pathlib import Path
p=Path(__file__).resolve().parents[1]/"server/app.py"
s=p.read_text(encoding="utf-8")
assert 'f"const API_BASE={json.dumps(relay_base)};\\n" + anchor' in s
assert 'f"const API_BASE={json.dumps(relay_base)};\\\\n" + anchor' not in s
assert "FABRIC_HOST_SHELL_REWRITE_FAILED" in s
print("P34.1J HOST SHELL JS PARSE FIX: PASS")
