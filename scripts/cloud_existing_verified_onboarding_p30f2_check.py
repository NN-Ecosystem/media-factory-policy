"""P30F.2 deterministic check: existing verified account requires activation proof, does not reset Trial."""
import time
from server.services.cloud_foundation_service import CloudFoundationService
from server.services.cloud_errors import CloudFoundationError

NOW = int(time.time())

class Users:
    def __init__(self):
        self.d={'u1':{'user_id':'u1','email':'real@example.com','status':'active','email_verified_at':NOW-3600}}
    def create_or_get(self,email): return dict(self.d['u1'])
    def get(self,uid): return dict(self.d.get(uid) or {}) or None
    def mark_verified(self,uid,at): self.d[uid].update(status='active',email_verified_at=at)

class Vers:
    def __init__(self): self.d={}; self.n=0
    def create(self,uid,email,token,ttl_seconds=1800,purpose='trial_verification'):
        self.n+=1; vid=f'v{self.n}'
        self.d[vid]={'verification_id':vid,'user_id':uid,'email':email,'token':token,'status':'pending','purpose':purpose,'expires_at':NOW+ttl_seconds}
        return dict(self.d[vid])
    def find_by_token(self,t): return next((dict(v) for v in self.d.values() if v['token']==t),None)
    def get(self,vid): return dict(self.d.get(vid) or {}) or None
    def mark_verified(self,vid,at): self.d[vid].update(status='verified',verified_at=at)

class Trials:
    def __init__(self): self.d={'u1':{'trial_id':'t1','user_id':'u1','started_at':NOW-3600,'expires_at':NOW+10*86400,'status':'active'}}
    def activate_once(self,uid,at,days): return dict(self.d[uid])
    def get(self,uid): return dict(self.d.get(uid) or {}) or None

class Ents:
    def __init__(self): self.e={'entitlement_id':'e1','subject_id':'u1','product':'core','plan':'trial','source_type':'trial','source_id':'t1','starts_at':NOW-3600,'expires_at':NOW+10*86400,'status':'active'}
    def issue_once(self,*args,**kwargs): return dict(self.e)
    def active_for_user(self,uid,now=None): return [dict(self.e)] if uid=='u1' else []

class Cores:
    def __init__(self): self.d={}
    def register(self,uid,cid,ver,mh):
        cid=cid or 'c-new'; secret='secret-new'; self.d[cid]={'core_id':cid,'user_id':uid,'status':'active','core_secret_hash':'x','core_version':ver}; return dict(self.d[cid]),secret
    def get(self,cid): return dict(self.d.get(cid) or {}) or None
    def verify_secret(self,cid,s): return cid in self.d and s=='secret-new'

class Sessions:
    def __init__(self): self.d={}; self.n=0
    def create(self,uid,email,vid,ttl):
        self.n+=1; sid=f's{self.n}'; rec={'session_id':sid,'user_id':uid,'email':email,'verification_id':vid,'secret_hash':'h','status':'pending_verification','expires_at':NOW+ttl,'core_id':None}; self.d[sid]=rec; return dict(rec),'onboard-secret'
    def verify(self,sid,secret): return dict(self.d[sid]) if sid in self.d and secret=='onboard-secret' else None
    def update_status(self,sid,status,**extra): self.d[sid].update(status=status,**extra)
    def set_verification(self,sid,vid): self.d[sid].update(verification_id=vid,status='pending_verification')
    def mark_completed(self,sid,cid): self.d[sid].update(status='completed',core_id=cid)

class Mail:
    def __init__(self): self.sent=[]
    def send_verification(self,**kw): self.sent.append(kw)
class Signer:
    def sign(self,p): return 'sig'

users=Users(); trials=Trials(); vers=Vers(); sessions=Sessions(); mail=Mail()
svc=CloudFoundationService(users,vers,trials,Ents(),Cores(),Signer(),email_delivery=mail,onboarding_sessions=sessions)
original_started=trials.d['u1']['started_at']; original_exp=trials.d['u1']['expires_at']
r,token=svc.register('real@example.com', deliver_email=False)
assert r['account_state']=='existing_verified'
assert r['verification_required'] is False
assert r['activation_confirmation_required'] is True
assert r['verification_purpose']=='core_activation'
assert r['trial_activation_required'] is False
st=svc.onboarding_status(r['onboarding_session_id'], r['onboarding_secret'])
assert st['state']=='pending_activation_confirmation'
assert st['email_verified'] is True
assert st['activation_confirmed'] is False
try:
    svc.complete_onboarding(r['onboarding_session_id'], r['onboarding_secret'], core_version='3.2.0')
    raise AssertionError('fresh Core must not activate from email address alone')
except CloudFoundationError as exc:
    assert exc.code=='EMAIL_NOT_VERIFIED'
verified=svc.verify_email(token)
assert verified['account_was_verified'] is True
assert verified['verification_purpose']=='core_activation'
assert trials.d['u1']['started_at']==original_started and trials.d['u1']['expires_at']==original_exp
st2=svc.onboarding_status(r['onboarding_session_id'], r['onboarding_secret'])
assert st2['state']=='activation_confirmed' and st2['activation_confirmed'] is True
out=svc.complete_onboarding(r['onboarding_session_id'], r['onboarding_secret'], core_version='3.2.0')
assert out['completed'] is True and out['core']['core_secret']=='secret-new'
print('P30F2-EXISTING-VERIFIED-ACCOUNT-CHECK PASSED')
