from server.services.cloud_access_policy import CloudAccessPolicy
class Repo:
    def get(self, plan):
        return {"schema":"core_plan_policy_v1","plan":plan,"policy_version":1,
                "enabled":True,"quota_class":"metered","capability_policy":"full",
                "quotas":{"pipeline_runs_per_day":4,"saved_pipelines":4,
                          "plugin_runtime_hours_per_day_per_plugin":4}}
p=CloudAccessPolicy(plan_policy_repo=Repo())
u=p.usage_policy_projection([{"product":"core","plan":"trial","source_type":"trial","entitlement_id":"e1"}])
assert u["quota_class"]=="metered"
assert u["limits"]["pipeline_runs_per_day"]==4
assert u["limits"]["saved_pipelines"]==4
assert u["limits"]["plugin_runtime_hours_per_day_per_plugin"]==4
assert u["pipeline_runs_per_day"]==4
print("P35 signed plan policy limits: PASS")
