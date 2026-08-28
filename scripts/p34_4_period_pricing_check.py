from server.services.cloud_access_policy import CloudAccessPolicy
class P(CloudAccessPolicy):
 def resolve_effective_plan_policy(self,ents):
  return {'enabled':True,'plan':'pro','credit_policy':{'enabled':True,'required_actions':['plugin.run'],'pricing':{'plugin.run':{'mode':'per_period','credits':3,'period_seconds':3600}}},'quotas':{}}
p=P(); r=p.resolve_usage_charge([{'product':'core','plan':'pro','status':'active'}],action='plugin.run',item_type='plugin',item_id='x',units=1)
assert r['allowed'] and r['mode']=='per_period' and r['credits']==3 and r['period_seconds']==3600
print('P34.4 CLOUD PERIOD PRICING: PASS')
