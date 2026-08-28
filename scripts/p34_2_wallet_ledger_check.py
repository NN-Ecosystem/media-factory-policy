"""Core Factory 3.4 P34.2 Wallet + Ledger behavioral acceptance."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import google.cloud
class _FirestoreShim:
    @staticmethod
    def transactional(fn): return lambda tx, *a, **k: fn(tx, *a, **k)
firestore = _FirestoreShim()
google.cloud.firestore = firestore
from server.repositories.wallet_repository import WalletRepository
from server.services.wallet_service import WalletService
from server.services.cloud_errors import CloudFoundationError


class Snap:
    def __init__(self, key, data):
        self.id = key.split("/")[-1]
        self._data = None if data is None else dict(data)
        self.exists = data is not None
    def to_dict(self):
        return None if self._data is None else dict(self._data)


class Ref:
    def __init__(self, db, key): self.db=db; self.key=key
    def get(self, transaction=None): return Snap(self.key, self.db.data.get(self.key))
    def set(self, data): self.db.data[self.key]=dict(data)
    def update(self, patch):
        cur=dict(self.db.data.get(self.key) or {}); cur.update(dict(patch)); self.db.data[self.key]=cur
    def collection(self, name): return Collection(self.db, f"{self.key}/{name}")


class Query:
    def __init__(self, db, prefix): self.db=db; self.prefix=prefix; self.n=50
    def order_by(self, *_args, **_kwargs): return self
    def limit(self, n): self.n=int(n); return self
    def stream(self):
        rows=[]
        prefix=self.prefix+"/"
        for key,data in self.db.data.items():
            if key.startswith(prefix) and "/" not in key[len(prefix):]: rows.append(Snap(key,data))
        rows.sort(key=lambda s:int((s.to_dict() or {}).get("created_at") or 0), reverse=True)
        return rows[:self.n]


class Collection:
    def __init__(self, db, prefix): self.db=db; self.prefix=prefix
    def document(self, doc_id): return Ref(self.db, f"{self.prefix}/{doc_id}")
    def order_by(self, *_args, **_kwargs): return Query(self.db,self.prefix)


class Tx:
    def __init__(self, db): self.db=db
    def set(self, ref, data): self.db.data[ref.key]=dict(data)
    def update(self, ref, patch):
        cur=dict(self.db.data.get(ref.key) or {}); cur.update(dict(patch)); self.db.data[ref.key]=cur


class DB:
    def __init__(self): self.data={}
    def collection(self, name): return Collection(self,name)
    def transaction(self): return Tx(self)


db=DB(); repo=WalletRepository(db); service=WalletService(repo)
user="u1"
wallet=service.ensure_wallet(user)
assert wallet["available_credits"]==0

grant=service.grant(user_id=user,amount=500,source="trial_grant",reference_type="trial",reference_id="t1",idempotency_key="trial:t1")
assert grant["type"]=="grant"
assert service.get_balance(user)["available_credits"]==500
# Retry same grant: no double credit.
service.grant(user_id=user,amount=500,source="trial_grant",reference_type="trial",reference_id="t1",idempotency_key="trial:t1")
assert service.get_balance(user)["available_credits"]==500

res=service.reserve(user_id=user,amount=10,reference_type="plugin_run",reference_id="exec-1",idempotency_key="exec-1")
assert res["remaining_credits"]==10
assert service.get_balance(user)["available_credits"]==490
assert service.get_balance(user)["reserved_credits"]==10
# Retry reserve: same reservation/no double debit.
res2=service.reserve(user_id=user,amount=10,reference_type="plugin_run",reference_id="exec-1",idempotency_key="exec-1")
assert res2["reservation_id"]==res["reservation_id"]
assert service.get_balance(user)["available_credits"]==490

cap=service.capture(user_id=user,reservation_id=res["reservation_id"],amount=7,idempotency_key="exec-1:capture",release_remainder=True)
assert cap["amount"]==7 and cap["released_remainder_credits"]==3
bal=service.get_balance(user)
assert bal["available_credits"]==493 and bal["reserved_credits"]==0
# Retry capture is idempotent.
service.capture(user_id=user,reservation_id=res["reservation_id"],amount=7,idempotency_key="exec-1:capture",release_remainder=True)
assert service.get_balance(user)["available_credits"]==493

res3=service.reserve(user_id=user,amount=5,reference_type="node_run",reference_id="exec-2",idempotency_key="exec-2")
service.release(user_id=user,reservation_id=res3["reservation_id"],amount=None,idempotency_key="exec-2:release")
assert service.get_balance(user)["available_credits"]==493

refund=service.refund(user_id=user,amount=2,reference_type="execution",reference_id="exec-3",idempotency_key="exec-3:refund")
assert refund["type"]=="refund"
assert service.get_balance(user)["available_credits"]==495

try:
    service.reserve(user_id=user,amount=999,reference_type="plugin_run",reference_id="nope",idempotency_key="nope")
    raise AssertionError("Expected insufficient credit")
except CloudFoundationError as exc:
    assert exc.code=="INSUFFICIENT_CREDIT"

items=service.list_transactions(user,limit=20)["items"]
assert any(x.get("type")=="grant" for x in items)
assert any(x.get("type")=="reserve" for x in items)
assert any(x.get("type")=="capture" for x in items)
assert any(x.get("type")=="release" for x in items)
assert any(x.get("type")=="refund" for x in items)
print("P34.2 WALLET + LEDGER: PASSED")
