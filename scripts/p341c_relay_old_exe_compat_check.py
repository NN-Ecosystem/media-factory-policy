from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'server/app.py').read_text(encoding='utf-8')
assert 'if request.url.query and local_pathname != "/"' in app
assert 'fetch(API_BASE+path' in app
assert 'fetch(API_BASE+d.path' in app
print('CLOUD 3.4.1C OLD-EXE RELAY COMPAT: PASS')
