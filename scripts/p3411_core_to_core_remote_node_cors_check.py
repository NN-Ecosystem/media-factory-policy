from pathlib import Path
app=Path("server/app.py").read_text(encoding="utf-8")
assert "allow_origin_regex=_core_loopback_origin_regex" in app
assert "localhost" in app and "127\\.0\\.0\\.1" in app and "\\[::1\\]" in app
assert 'allow_origins=["*"]' not in app
assert 'allow_credentials=False' in app
print("P34.11 Core-to-Core remote Node loopback CORS: PASS")
