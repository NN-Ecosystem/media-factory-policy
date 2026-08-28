from pathlib import Path

repo = Path(__file__).resolve().parents[1] / "server" / "repositories" / "credit_order_repository.py"
text = repo.read_text(encoding="utf-8")

assert 'collection_group("orders")' in text, "V2 admin list must read canonical account orders"
assert 'current_status != wanted_status' in text, "Admin status filter must use canonical document state"
assert 'self.legacy_ref(order_id).set(body, merge=True)' in text, "v2_compat patch must synchronize legacy shadow"
assert 'if self.v2.v2 and self.v2.legacy_shadow_write' in text
print("P34 DATA V2 CREDIT ORDER STATE: PASS")
