from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import types
errors=types.ModuleType("server.services.cloud_errors")
class CloudFoundationError(RuntimeError):
    def __init__(self, code, message, status_code=400): self.code=code; self.message=message; self.status_code=status_code; super().__init__(code)
errors.CloudFoundationError=CloudFoundationError
sys.modules["server.services.cloud_errors"]=errors
from server.services.credit_order_service import CreditOrderService


class FakeRepo:
    def __init__(self): self.orders={}
    def create_or_get(self, *, user_id, package, idempotency_key):
        oid='ord_'+idempotency_key
        if oid not in self.orders:
            self.orders[oid]={
                'order_id':oid,'user_id':user_id,'package_id':package['package_id'],
                'credits':package['credits'],'currency':package['currency'],'price_minor':package['price_minor'],
                'status':'pending','created_at':1,
            }
        return dict(self.orders[oid])
    def get(self, oid): return dict(self.orders[oid]) if oid in self.orders else None
    def patch(self, oid, patch): self.orders[oid].update(patch); return dict(self.orders[oid])
    def list_for_user(self,user_id,limit=30): return [dict(v) for v in self.orders.values() if v['user_id']==user_id][:limit]
    def list_admin(self,status='',limit=100): return [dict(v) for v in self.orders.values() if not status or v['status']==status][:limit]

class FakeWallet:
    def __init__(self): self.calls=[]; self.keys={}
    def grant(self, **kw):
        key=kw['idempotency_key']
        if key not in self.keys:
            self.calls.append(dict(kw)); self.keys[key]={'transaction_id':'tx_'+str(len(self.calls)),'amount':kw['amount']}
        return dict(self.keys[key])

class FakeUsers:
    def get(self, uid): return {'user_id':uid,'email':'user@example.com'}

repo=FakeRepo(); wallet=FakeWallet(); service=CreditOrderService(repo,wallet,FakeUsers())
cat=service.catalog(); assert [(x['credits'],x['price_minor']) for x in cat['items']]==[(100,500),(250,1000),(600,2000),(1750,5000),(4000,10000)]
a=service.create(user_id='u1',package_id='CORE_CREDIT_1200',idempotency_key='same')
b=service.create(user_id='u1',package_id='CORE_CREDIT_1200',idempotency_key='same')
assert a['order']['order_id']==b['order']['order_id'] and len(repo.orders)==1
assert wallet.calls==[]  # creating an order never grants Credit
r1=service.approve_manual(order_id=a['order']['order_id'],admin_actor='owner',reason='paid manually')
r2=service.approve_manual(order_id=a['order']['order_id'],admin_actor='owner',reason='retry')
assert len(wallet.calls)==1 and r1['order']['status']=='completed' and r2['order']['status']=='completed'
assert wallet.calls[0]['source']=='manual_topup' and wallet.calls[0]['amount']==600
print('P34.5 CREDIT PACKAGES + ORDERS: PASS')
