from server.services.cloud_access_policy import CloudAccessPolicy
from server.services.payment_gateway import ManualOnlyPaymentGateway, AutomaticPaymentDisabled

class Repo:
    def get(self, plan):
        return {
            "schema":"core_plan_policy_v1","plan":plan,"enabled":True,
            "credit_policy":{
                "enabled":True,
                "required_actions":["plugin.run","pipeline.run","node.run"],
                "pricing":{
                    "plugin.run":{"mode":"per_run","credits":2},
                    "pipeline.run":{"mode":"per_workload","credits":2},
                    "node.run":{"mode":"per_period","credits":3,"period_seconds":3600},
                },
            },
            "payment":{"mode":"manual","automatic_enabled":False},
        }

p=CloudAccessPolicy(plan_policy_repo=Repo())
ents=[{"entitlement_id":"e1","product":"core","status":"active","plan":"pro","source_type":"manual"}]
# Flat PER_RUN pricing is exactly one unit even if callers supply workload hints.
r=p.resolve_usage_charge(ents,action="plugin.run",item_type="plugin",item_id="p1",units=2)
assert r["required"] and r["allowed"] and r["credits"]==2 and r["units"]==1 and r["mode"]=="per_run"
# PER_WORKLOAD is the only V1 mode that scales by caller workload units.
r=p.resolve_usage_charge(ents,action="pipeline.run",item_type="pipeline",item_id="pipe1",units=3)
assert r["required"] and r["allowed"] and r["credits"]==6 and r["units"]==3 and r["mode"]=="per_workload"
r=p.resolve_usage_charge(ents,action="engine.execute",item_type="engine",item_id="e1")
assert not r["required"] and r["credits"]==0
r=p.resolve_usage_charge(ents,action="node.run",item_type="node",item_id="n1")
assert r["required"] and r["allowed"] and r["mode"]=="per_period" and r["credits"]==3 and r["period_seconds"]==3600

g=ManualOnlyPaymentGateway(); assert g.status()["automatic_enabled"] is False
try: g.handle_provider_event()
except AutomaticPaymentDisabled: pass
else: raise AssertionError("automatic payment must remain disabled")
print("P34.3 CLOUD USAGE AUTHORIZATION: PASSED")
