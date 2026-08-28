# Cloud — Per-Item Runtime + Credit Policy

`credit_policy.item_policies[item_id]` can now declare runtime lifecycle semantics and canonical action pricing.
An explicit item action with `mode=free` overrides the generic action price. Other item actions can be per_run/per_workload/per_period without changing Core code.
Personal Assistant baseline: ambient, no user Start/Stop, no idle billing; explicit speech/translation/document/smart actions are declared as per-run policy entries.
Cloud remains pricing authority; Core only projects/presents/enforces the signed policy.
