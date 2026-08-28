from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/"server/repositories/core_repository.py").read_text(encoding="utf-8")
assert "def _legacy_ref" in s
legacy_block=s.split("def _legacy_ref",1)[1].split("def _account_for_core",1)[0]
assert "self._ref(" not in legacy_block
assert "self.db.collection(self.COLLECTION).document" in legacy_block
account_block=s.split("def _account_for_core",1)[1].split("def _ref(",1)[0]
assert "self._legacy_ref(core_id).get()" in account_block
assert "return self._ref(" not in account_block
print("CLOUD D3B CORE REF RECURSION HOTFIX: PASS")
