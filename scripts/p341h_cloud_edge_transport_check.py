from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
fabric=(ROOT/"server/services/fabric_service.py").read_text(encoding="utf-8")
for n in [
    "window.fetch=function(input,init)",
    "input.indexOf('/api/v1/client/')===0",
    "input=b+input",
    "__CORE_FACTORY_RELAY_BASE__",
    '/v1/cloud/host/{public_host_id}/',
]:
    assert n in app, n
assert "future.cancel()" in fabric
assert "future.set_exception(exc)" not in fabric
print("CLOUD 3.4.1H EDGE TRANSPORT COMPAT: PASS")
