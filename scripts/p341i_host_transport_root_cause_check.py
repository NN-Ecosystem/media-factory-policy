from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
fabric=(ROOT/"server/services/fabric_service.py").read_text(encoding="utf-8")
assert "import json" in app
assert 'r"const\\s+API_BASE\\s*=\\s*[^;]+;"' in app
assert "FABRIC_HOST_SHELL_REWRITE_FAILED" in app
assert "Host relay HTML transport rewrite failed" in app
assert "future.set_exception(exc)" not in fabric
print("P34.1I HOST TRANSPORT ROOT-CAUSE CHECK: PASS")
