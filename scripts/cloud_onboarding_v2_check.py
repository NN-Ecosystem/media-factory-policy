"""Deterministic contract check for Cloud V2 email onboarding."""
import time
from server.services.cloud_foundation_service import CloudFoundationService
from server.services.cloud_errors import CloudFoundationError

class Users:
    def __init__(self): self.d={}
    def create_or_get(self,email):
        uid='u1'; self.d.setdefault(uid,{'user_id':uid,'email':email.lower(),'status':'pending_verification','email_verified_at':None}); return dict(self.d[uid])
    def get(self,uid): return dict(self.d.get(uid) or {}) or None
    def mark_verified(self,uid,at): self.d[uid].update(status='active',email_verified_at=at)
class Vers:
    def __init__(self): self.d={}; self.n=0
    def create(self,uid,email,token,ttl_seconds=1800):
        self.n+=1; vid=f'v{self.n}'; self.d[vid]={'verification_id':vid,'user_id':uid,'email':email,'token':token,'status':'pending','expires_at':int(time.time())+ttl_seconds}; return dict(self.d[vid])
    def find_by_token(self,t): return next((dict(v) for v in self.d.values() if v['token']==t),None)
    def get(self,vid): return dict(self.d.get(vid) or {}) or None
    def mark_verified(self,vid,at): self.d[vid].update(status='verified',verified_at=at)
class Trials:
    def __init__(self): self.d={}
    def activate_once(self,uid,at,days): self.d.setdefault(uid,{'trial_id':'t1','user_id':uid,'started_at':at,'expires_at':at+days*86400,'status':'active'}); return dict(self.d[uid])
    def get(self,uid): return dict(self.d.get(uid) or {}) or None
class Ents:
    def __init__(self): self.d=[]
    def issue_once(self,uid,product,plan,source,sid,start,exp):
        if not self.d:self.d.append({'entitlement_id':'e1','subject_id':uid,'product':product,'plan':plan,'source_type':source,'source_id':sid,'starts_at':start,'expires_at':exp,'status':'active'})
        return dict(self.d[0])
    def active_for_user(self,uid,now=None): return [dict(e) for e in self.d if e['subject_id']==uid and e['status']=='active']
class Cores:
    def __init__(self): self.d={}
    def register(self,uid,cid,ver,mh):
        cid=cid or 'c1'; secret='secret'; self.d[cid]={'core_id':cid,'user_id':uid,'status':'active','core_secret_hash':'x','core_version':ver}; return dict(self.d[cid]),secret
    def get(self,cid): return dict(self.d.get(cid) or {}) or None
    def verify_secret(self,cid,s): return cid in self.d and s=='secret'
class Sessions:
    def __init__(self): self.d={}
    def create(self,uid,email,vid,ttl):
        rec={'session_id':'s1','user_id':uid,'email':email,'verification_id':vid,'secret_hash':'h','status':'pending_verification','expires_at':int(time.time())+ttl,'core_id':None}; self.d['s1']=rec; return dict(rec),'onboard-secret'
    def verify(self,sid,secret): return dict(self.d[sid]) if sid in self.d and secret=='onboard-secret' else None
    def update_status(self,sid,status,**extra): self.d[sid].update(status=status,**extra)
    def set_verification(self,sid,vid): self.d[sid].update(verification_id=vid,status='pending_verification')
    def mark_completed(self,sid,cid): self.d[sid].update(status='completed',core_id=cid)
class Mail:
    def __init__(self): self.sent=[]
    def send_verification(self,**kw): self.sent.append(kw)
class Signer:
    def sign(self,p): return 'sig'

svc=CloudFoundationService(Users(),Vers(),Trials(),Ents(),Cores(),Signer(),email_delivery=Mail(),onboarding_sessions=Sessions())
r,token=svc.register('real@example.com')
assert r['onboarding_session_id']=='s1' and r['onboarding_secret']=='onboard-secret'
assert svc.onboarding_status('s1','onboard-secret')['email_verified'] is False
try:
    svc.complete_onboarding('s1','onboard-secret',core_version='3.2.0')
    raise AssertionError('complete must deny before email verification')
except CloudFoundationError as exc:
    assert exc.code=='EMAIL_NOT_VERIFIED'
svc.verify_email(token)
st=svc.onboarding_status('s1','onboard-secret')
assert st['email_verified'] is True and st['trial']['status']=='active'
out=svc.complete_onboarding('s1','onboard-secret',core_version='3.2.0')
assert out['completed'] is True and out['core']['core_secret']=='secret' and out['access_grant']['payload']['access']['plan']=='trial'
print('CLOUD-ONBOARDING-V2-CHECK PASSED')
