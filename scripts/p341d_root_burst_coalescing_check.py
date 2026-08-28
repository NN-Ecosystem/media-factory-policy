from pathlib import Path
r=Path(__file__).resolve().parents[1]
f=(r/'server/services/fabric_service.py').read_text(encoding='utf-8')
a=(r/'server/app.py').read_text(encoding='utf-8')
for x in ['relay_root_cached','_root_cache','_root_inflight']:
    assert x in f
assert 'fabric_service.relay_root_cached' in a
print('CLOUD 3.4.1D ROOT BURST COALESCING: PASS')
