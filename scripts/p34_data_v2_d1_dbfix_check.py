from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/"server/app.py").read_text(encoding="utf-8")
assert "def _data_v2_db():" in s
assert "from server.db.firebase import get_db" in s
assert "DataMigrationInventory(_data_v2_db())" in s
assert "DataMigrationInventory(db)" not in s
print("CLOUD DATA V2 D1 FIRESTORE RESOLUTION FIX: PASS")
