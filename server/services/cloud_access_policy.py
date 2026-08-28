import os
import time
import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


CORE_PRODUCT = "core"

CANONICAL_PLANS = ("trial", "basic", "pro", "master")

CANONICAL_CREDIT_MODES = ("free", "per_run", "per_workload", "per_period", "unlock", "metered")

CORE34_SIMPLE_CREDIT_POLICY = {
    "enabled": True,
    "required_actions": ["pipeline.run", "plugin.run", "node.run"],
    "pricing": {
        "pipeline.run": {"mode": "per_run", "credits": 1},
        "plugin.run": {"mode": "per_period", "credits": 3, "period_seconds": 3600},
        "node.run": {"mode": "per_period", "credits": 7, "period_seconds": 3600},
    },
    "item_pricing": {},
    # Per-item policy can override lifecycle and pricing without Core hard-coding an item.
    # actions is keyed by canonical usage action and may explicitly declare mode=free.
    "item_policies": {},
    "trial_grant_credits": 200,
}

def _configured_item_policies() -> Dict:
    """Load deploy-time per-item runtime/credit policy without hard-coding items in Core.

    Precedence: bundled deployment config < CLOUD_ITEM_USAGE_POLICIES_JSON.
    Firestore plan policy can still override this later through normal policy merging.
    """
    merged: Dict = {}
    try:
        path = Path(__file__).resolve().parents[2] / "item_usage_policies.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict): merged.update(dict(raw.get("item_policies") or raw))
    except Exception:
        pass
    try:
        env = str(os.getenv("CLOUD_ITEM_USAGE_POLICIES_JSON", "") or "").strip()
        if env:
            raw = json.loads(env)
            if isinstance(raw, dict): merged.update(dict(raw.get("item_policies") or raw))
    except Exception:
        pass
    return merged

def _credit_policy_default() -> Dict:
    # Generic defaults only. Per-item behavior is data-driven via deployment/Cloud policy.
    return {
        **CORE34_SIMPLE_CREDIT_POLICY,
        "item_policies": _configured_item_policies(),
        "supported_modes": list(CANONICAL_CREDIT_MODES),
        "payment": {"mode": "manual", "automatic_enabled": False},
    }

DEFAULT_PLAN_POLICIES = {
    "trial": {"schema":"core_plan_policy_v1","plan":"trial","policy_version":2,"enabled":True,"quota_class":"unlimited","capability_policy":"full","quotas":{},"credit_policy":dict(CORE34_SIMPLE_CREDIT_POLICY)},
    "basic": {"schema":"core_plan_policy_v1","plan":"basic","policy_version":2,"enabled":True,"quota_class":"unlimited","capability_policy":"plan","quotas":{},"credit_policy":dict(CORE34_SIMPLE_CREDIT_POLICY)},
    "pro": {"schema":"core_plan_policy_v1","plan":"pro","policy_version":2,"enabled":True,"quota_class":"unlimited","capability_policy":"plan","quotas":{},"credit_policy":dict(CORE34_SIMPLE_CREDIT_POLICY)},
    "master": {"schema":"core_plan_policy_v1","plan":"master","policy_version":2,"enabled":True,"quota_class":"unlimited","capability_policy":"full","quotas":{},"credit_policy":dict(CORE34_SIMPLE_CREDIT_POLICY)},
}
LEGACY_PLAN_MAP = {
    "trial": "trial",
    "free": "basic",
    "personal": "basic",
    "basic": "basic",
    "team": "pro",
    "pro": "pro",
    "enterprise": "master",
    "int": "master",
    "master": "master",
}

def canonical_plan(value: object) -> str:
    raw = str(value or "").strip().lower()
    return LEGACY_PLAN_MAP.get(raw, raw)

CORE_PERMISSIONS = (
    "core.view",
    "core.execute",
    "engine.execute",
    "pipeline.run",
    "plugin.run",
    "node.access",
    "runtime.distribution.resolve",
    "runtime.distribution.download",
)


class CloudAccessPolicy:
    """Projects authoritative entitlements into a signed Core access policy.

    Cloud owns commercial access policy.  Core consumes the signed projection
    and must not invent Trial quota/capability defaults locally.
    """

    def __init__(
        self,
        *,
        offline_allowed: bool = True,
        offline_max_seconds: int = 43200,
        trial_pipeline_runs_per_day: int = 1,
        trial_plugin_hours_per_day_per_plugin: int = 2,
        trial_engine_jobs_per_day_per_engine: int = 5,
        trial_engine_ids: Optional[List[str]] = None,
        trial_plugin_ids: Optional[List[str]] = None,
        trial_node_service_ids: Optional[List[str]] = None,
        trial_policy_loader: Optional[Callable[[], Dict]] = None,
        plan_policy_repo=None,
        entitlement_override_repo=None,
    ):
        self.offline_allowed = bool(offline_allowed)
        self.offline_max_seconds = max(0, int(offline_max_seconds))
        self.trial_pipeline_runs_per_day = max(0, int(trial_pipeline_runs_per_day))
        self.trial_plugin_hours_per_day_per_plugin = max(0, int(trial_plugin_hours_per_day_per_plugin))
        self.trial_engine_jobs_per_day_per_engine = max(0, int(trial_engine_jobs_per_day_per_engine))
        self.trial_engine_ids = self._clean_ids(trial_engine_ids)
        self.trial_plugin_ids = self._clean_ids(trial_plugin_ids)
        self.trial_node_service_ids = self._clean_ids(trial_node_service_ids)
        self.trial_policy_loader = trial_policy_loader
        self.plan_policy_repo = plan_policy_repo
        self.entitlement_override_repo = entitlement_override_repo
        self._plan_policy_cache = {}
        self._plan_policy_cache_ttl = max(
            0, int(os.getenv("CLOUD_PLAN_POLICY_CACHE_SECONDS", "60"))
        )

    @staticmethod
    def _clean_ids(values: Optional[Iterable[str]]) -> Optional[List[str]]:
        if values is None:
            return None
        result = []
        seen = set()
        for value in values:
            item = str(value or "").strip()
            if item and item not in seen:
                result.append(item)
                seen.add(item)
        return result

    @staticmethod
    def _csv_env(name: str) -> Optional[List[str]]:
        raw = os.getenv(name)
        if raw is None or not raw.strip():
            return None
        return [part.strip() for part in raw.split(",") if part.strip()]

    @classmethod
    def from_env(cls, trial_policy_loader: Optional[Callable[[], Dict]] = None, plan_policy_repo=None, entitlement_override_repo=None) -> "CloudAccessPolicy":
        allowed = os.getenv("CLOUD_OFFLINE_ACCESS_ALLOWED", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }
        max_seconds = int(os.getenv("CLOUD_OFFLINE_MAX_SECONDS", "43200"))
        return cls(
            offline_allowed=allowed,
            offline_max_seconds=max_seconds,
            trial_pipeline_runs_per_day=int(os.getenv("CLOUD_TRIAL_PIPELINE_RUNS_PER_DAY", "1")),
            trial_plugin_hours_per_day_per_plugin=int(os.getenv("CLOUD_TRIAL_PLUGIN_HOURS_PER_DAY_PER_PLUGIN", "2")),
            trial_engine_jobs_per_day_per_engine=int(os.getenv("CLOUD_TRIAL_ENGINE_JOBS_PER_DAY_PER_ENGINE", "5")),
            trial_engine_ids=cls._csv_env("CLOUD_TRIAL_ENGINE_IDS"),
            trial_plugin_ids=cls._csv_env("CLOUD_TRIAL_PLUGIN_IDS"),
            trial_node_service_ids=cls._csv_env("CLOUD_TRIAL_NODE_SERVICE_IDS"),
            trial_policy_loader=trial_policy_loader,
            plan_policy_repo=plan_policy_repo,
            entitlement_override_repo=entitlement_override_repo,
        )

    @staticmethod
    def _core_entitlements(entitlements: Iterable[Dict]) -> List[Dict]:
        return [
            e for e in (entitlements or [])
            if e.get("product") == CORE_PRODUCT and e.get("status", "active") == "active"
        ]

    @staticmethod
    def _effective_core_entitlement(entitlements: Iterable[Dict]) -> Optional[Dict]:
        candidates = CloudAccessPolicy._core_entitlements(entitlements)
        if not candidates:
            return None

        # Prefer the same commercial precedence used by account activation so
        # an overlapping Trial cannot outrank a paid/manual/legacy entitlement.
        source_priority = {
            "payment": 50,
            "manual": 40,
            "legacy_license": 30,
            "promo": 20,
            "trial": 10,
        }

        def rank(e: Dict):
            exp = e.get("expires_at")
            return (
                source_priority.get(str(e.get("source_type") or ""), 0),
                1 if exp is None else 0,
                int(exp or 0),
                int(e.get("starts_at") or 0),
            )

        return max(candidates, key=rank)

    @staticmethod
    def _is_trial_entitlement(entitlement: Optional[Dict]) -> bool:
        if not entitlement:
            return False
        return (
            str(entitlement.get("source_type") or "").strip().lower() == "trial"
            or str(entitlement.get("plan") or "").strip().lower() == "trial"
        )

    def _load_plan_policy(self, plan: str) -> Dict:
        plan=canonical_plan(plan)
        base=dict(DEFAULT_PLAN_POLICIES.get(plan) or {})
        base["quotas"]=dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("quotas") or {})
        base["feature_flags"]=dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("feature_flags") or {})
        base["credit_policy"]={**_credit_policy_default(), **dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("credit_policy") or {})}
        stored=None
        if self.plan_policy_repo is not None:
            now = time.monotonic()
            cached = self._plan_policy_cache.get(plan)
            if (
                cached
                and self._plan_policy_cache_ttl > 0
                and now - float(cached[0]) < self._plan_policy_cache_ttl
            ):
                stored = dict(cached[1] or {})
            else:
                try:
                    stored = self.plan_policy_repo.get(plan)
                except Exception:
                    stored = None
                self._plan_policy_cache[plan] = (now, dict(stored or {}))
        if stored:
            base.update(dict(stored))
            quotas=dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("quotas") or {})
            quotas.update(dict(stored.get("quotas") or {}))
            base["quotas"]=quotas
            flags=dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("feature_flags") or {})
            flags.update(dict(stored.get("feature_flags") or {}))
            base["feature_flags"]=flags
            credit={**_credit_policy_default(), **dict((DEFAULT_PLAN_POLICIES.get(plan) or {}).get("credit_policy") or {})}
            credit.update(dict(stored.get("credit_policy") or {}))
            credit["required_actions"]=[str(v) for v in (credit.get("required_actions") or []) if str(v)]
            base["credit_policy"]=credit
            base["policy_source"]="cloud_store"
        else:
            base["policy_source"]="bootstrap_default"
        return base

    def _apply_entitlement_override(self, policy: Dict, entitlement: Dict) -> Dict:
        effective=dict(policy or {})
        eid=str((entitlement or {}).get("entitlement_id") or "").strip()
        if not eid or self.entitlement_override_repo is None: return effective
        try: override=self.entitlement_override_repo.get(eid) or {}
        except Exception: override={}
        if not override or override.get("enabled",True) is False: return effective
        quotas=dict(effective.get("quotas") or {}); quotas.update(dict(override.get("quotas") or {})); effective["quotas"]=quotas
        flags=dict(effective.get("feature_flags") or {}); flags.update(dict(override.get("feature_flags") or {})); effective["feature_flags"]=flags
        credit={**_credit_policy_default(), **dict(effective.get("credit_policy") or {})}; credit.update(dict(override.get("credit_policy") or {})); credit["required_actions"]=[str(v) for v in (credit.get("required_actions") or []) if str(v)]; effective["credit_policy"]=credit
        for key in ("quota_class","capability_policy","permissions"):
            if key in override: effective[key]=override[key]
        effective["override"]={"schema":str(override.get("schema") or "core_entitlement_policy_override_v1"),"override_version":int(override.get("override_version") or 1),"entitlement_id":eid}
        return effective

    def trial_credit_grant(self) -> int:
        """Return the Cloud-authored Trial credit grant.

        The value belongs to Cloud policy, never Local Core. Stored plan policy
        may override the environment bootstrap value.
        """
        policy = self._load_plan_policy("trial")
        credit = dict(policy.get("credit_policy") or {})
        raw = credit.get("trial_grant_credits", os.getenv("CLOUD_TRIAL_CREDITS", "200"))
        try:
            return max(0, int(raw or 0))
        except Exception:
            return max(0, int(os.getenv("CLOUD_TRIAL_CREDITS", "200") or 0))

    def resolve_effective_plan_policy(self, entitlements: Iterable[Dict]) -> Optional[Dict]:
        entitlement=self._effective_core_entitlement(entitlements)
        if not entitlement: return None
        plan=canonical_plan(entitlement.get("plan"))
        policy=self._apply_entitlement_override(self._load_plan_policy(plan), entitlement)
        # Core 3.4 V1 intentionally removes commercial usage quotas. Preserve
        # technical/resource governance elsewhere, but make the signed product
        # policy Credit-only at the three explicit charge points.
        existing_credit = dict(policy.get("credit_policy") or {})
        simple_credit = {**_credit_policy_default()}
        simple_credit["item_pricing"] = dict(existing_credit.get("item_pricing") or {})
        default_item_policies = dict(simple_credit.get("item_policies") or {})
        default_item_policies.update(dict(existing_credit.get("item_policies") or {}))
        simple_credit["item_policies"] = default_item_policies
        policy["quota_class"] = "unlimited"
        policy["quotas"] = {}
        policy["credit_policy"] = simple_credit
        policy["plan"]=plan; policy["entitlement_id"]=entitlement.get("entitlement_id")
        return policy

    def permissions(self, entitlements: Iterable[Dict]) -> List[str]:
        policy=self.resolve_effective_plan_policy(entitlements)
        if not policy or not policy.get("enabled",True): return []
        if "permissions" in policy:
            return [v for v in list(policy.get("permissions") or []) if v in CORE_PERMISSIONS]
        plan=canonical_plan(policy.get("plan"))
        if plan in {"trial","master"}: return list(CORE_PERMISSIONS)
        defaults={
            "basic":["core.view","core.execute","engine.execute","pipeline.run","plugin.run","runtime.distribution.resolve","runtime.distribution.download"],
            "pro":["core.view","core.execute","engine.execute","pipeline.run","plugin.run","node.access","runtime.distribution.resolve","runtime.distribution.download"],
        }
        return list(defaults.get(plan,[]))

    def access_projection(self, entitlements: Iterable[Dict], *, grant_expires_at: int) -> Dict:
        e = self._effective_core_entitlement(entitlements)
        if not e:
            return {
                "state": "inactive",
                "product": CORE_PRODUCT,
                "plan": None,
                "source": None,
                "entitlement_id": None,
                "entitlement_expires_at": None,
                "grant_expires_at": int(grant_expires_at),
            }
        return {
            "state": "active",
            "product": e.get("product"),
            "plan": canonical_plan(e.get("plan")),
            "source": e.get("source_type"),
            "entitlement_id": e.get("entitlement_id"),
            "entitlement_expires_at": (
                None if canonical_plan(e.get("plan")) == "trial" else e.get("expires_at")
            ),
            "grant_expires_at": int(grant_expires_at),
        }

    def usage_policy_projection(self, entitlements: Iterable[Dict]) -> Optional[Dict]:
        effective=self.resolve_effective_plan_policy(entitlements)
        if not effective: return None
        if not effective.get("enabled",True):
            return {"schema":"core_usage_policy_v2","enabled":False,"plan":effective.get("plan"),"quota_class":"denied","reason":"plan_policy_disabled","fail_closed":True}
        projected={
            "schema":"core_usage_policy_v2",
            "enabled":True,
            "plan":effective.get("plan"),
            "policy_version":int(effective.get("policy_version") or 1),
            "policy_source":str(effective.get("policy_source") or "cloud_store"),
            "quota_class":str(effective.get("quota_class") or "metered"),
            "capability_policy":str(effective.get("capability_policy") or "plan"),
            "metering":{"mode":"root_invocation","child_invocations_metered":False,"engine_executions_metered":False,"core_jobs_metered":False},
            "quota_scope":"entitlement_activation_local_day",
            "fail_closed":True,
        }
        quotas = dict(effective.get("quotas") or {})
        # Canonical signed quota envelope for Core V3.3+.
        # Flat aliases remain during rollout for backward compatibility.
        projected["limits"] = dict(quotas)
        projected.update(quotas)
        if effective.get("override"): projected["override"]=dict(effective.get("override") or {})
        return projected

    def effective_usage_policy_projection(
        self,
        entitlements: Iterable[Dict],
        *,
        offline_policy: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Core 3.4 canonical economic + quota policy signed by Cloud.

        This envelope coexists with ``core_usage_policy_v2`` during the 3.3 ->
        3.4 migration.  It contains no authoritative wallet balance.
        """
        effective = self.resolve_effective_plan_policy(entitlements)
        if not effective:
            return None
        plan = canonical_plan(effective.get("plan"))
        enabled = bool(effective.get("enabled", True))
        credit = {**_credit_policy_default(), **dict(effective.get("credit_policy") or {})}
        credit["required_actions"] = [
            str(v) for v in (credit.get("required_actions") or []) if str(v)
        ]
        return {
            "schema": "core_effective_usage_policy_v1",
            "policy_version": int(effective.get("policy_version") or 1),
            "enabled": enabled,
            "access_class": plan or "cloud",
            "plan": plan or None,
            "policy_source": str(effective.get("policy_source") or "cloud_store"),
            "quota_class": (
                str(effective.get("quota_class") or "metered") if enabled else "denied"
            ),
            "capability_policy": str(effective.get("capability_policy") or "plan"),
            "limits": dict(effective.get("quotas") or {}),
            "feature_flags": dict(effective.get("feature_flags") or {}),
            "permissions": self.permissions(entitlements) if enabled else [],
            "credit_policy": credit,
            "credit_required_actions": list(credit.get("required_actions") or []),
            "offline_policy": dict(offline_policy or {}),
            "metering": {
                "mode": "root_invocation",
                "child_invocations_metered": False,
                "engine_executions_metered": False,
                "core_jobs_metered": False,
                "supported_credit_modes": list(CANONICAL_CREDIT_MODES),
            },
            "fail_closed": True,
        }


    def resolve_usage_charge(self, entitlements: Iterable[Dict], *, action: str, item_type: str = "", item_id: str = "", units: int = 1) -> Dict:
        """Resolve one chargeable root invocation from authoritative Cloud policy.

        Core never invents price. Per-period/metered modes are intentionally
        returned as deferred until the metering tranche owns duration settlement.
        """
        effective = self.resolve_effective_plan_policy(entitlements)
        if not effective or not effective.get("enabled", True):
            return {"required": False, "allowed": False, "code": "USAGE_NOT_ALLOWED"}
        credit = {**_credit_policy_default(), **dict(effective.get("credit_policy") or {})}
        action = str(action or "").strip()
        pricing = dict(credit.get("pricing") or {})
        rule = dict(pricing.get(action) or {})
        item_rules = dict(credit.get("item_pricing") or {})
        if item_id and isinstance(item_rules.get(item_id), dict):
            rule.update(dict(item_rules.get(item_id) or {}))

        item_policies = dict(credit.get("item_policies") or {})
        item_policy = dict(item_policies.get(str(item_id or "")) or {})
        explicit_action = dict((item_policy.get("actions") or {}).get(action) or {})
        if explicit_action:
            rule = explicit_action
            mode = str(rule.get("mode") or "free").strip().lower()
            if mode == "free":
                return {
                    "required": False, "allowed": True, "mode": "free", "credits": 0, "units": 0,
                    "action": action, "item_type": str(item_type or ""), "item_id": str(item_id or ""),
                }
            required = bool(credit.get("enabled", False))
        else:
            required = bool(credit.get("enabled", False) and action in set(credit.get("required_actions") or []))
            mode = str(rule.get("mode") or "").strip().lower()
        if not required:
            return {"required": False, "allowed": True, "mode": "free", "credits": 0, "units": 0}

        if mode not in CANONICAL_CREDIT_MODES or mode == "free":
            raise ValueError("USAGE_PRICING_UNAVAILABLE")
        if mode == "metered":
            return {"required": True, "allowed": False, "deferred": True, "code": "USAGE_METERING_NOT_READY", "mode": mode}
        try:
            unit_credits = int(rule.get("credits"))
            requested_units = max(1, int(units or 1))
            # PER_RUN/PER_PERIOD price one root invocation/period. Workload
            # scaling is applied only when the authoritative rule explicitly
            # selects PER_WORKLOAD. This prevents callers from multiplying a
            # flat run price by an incidental workload hint.
            resolved_units = requested_units if mode == "per_workload" else 1
        except Exception as exc:
            raise ValueError("USAGE_PRICING_INVALID") from exc
        if unit_credits <= 0:
            raise ValueError("USAGE_PRICING_INVALID")
        period_seconds = None
        if mode == "per_period":
            try:
                period_seconds = int(rule.get("period_seconds") or 3600)
            except Exception as exc:
                raise ValueError("USAGE_PRICING_INVALID") from exc
            if period_seconds < 60:
                raise ValueError("USAGE_PRICING_INVALID")
        return {
            "required": True, "allowed": True, "mode": mode,
            "credits": unit_credits * resolved_units, "unit_credits": unit_credits,
            "units": resolved_units, "action": action, "item_type": str(item_type or ""),
            "item_id": str(item_id or ""),
            "period_seconds": period_seconds,
            "billing_semantics": "commenced_period" if mode == "per_period" else None,
        }

    def trial_policy_projection(self, entitlements: Iterable[Dict]) -> Optional[Dict]:
        """Return the authoritative Trial policy for the signed access grant.

        Firestore-backed Cloud policy wins when available. Environment values
        are used only as a bootstrap fallback before a policy is authored.
        """
        effective = self._effective_core_entitlement(entitlements)
        if not self._is_trial_entitlement(effective):
            return None

        stored: Dict = {}
        if self.trial_policy_loader is not None:
            try:
                loaded = self.trial_policy_loader()
                stored = loaded if isinstance(loaded, dict) else {}
            except Exception:
                stored = {}

        if stored:
            if stored.get("enabled") is not True:
                return {
                    "schema": "core_trial_policy_v1",
                    "enabled": False,
                    "policy_source": "cloud_store",
                    "fail_closed": True,
                }
            raw_policy = stored.get("policy") if isinstance(stored.get("policy"), dict) else {}
            raw_access = stored.get("access") if isinstance(stored.get("access"), dict) else {}
            policy: Dict = {
                "schema": "core_trial_policy_v1",
                "enabled": True,
                "policy_source": "cloud_store",
                "pipeline_runs_per_day": int(raw_policy.get("pipeline_runs_per_day", 0) or 0),
                "plugin_hours_per_day_per_plugin": int(raw_policy.get("plugin_hours_per_day_per_plugin", 0) or 0),
                "quota_scope": "entitlement_activation_local_day",
                "trial_seat_limit": 1,
                "duration_days": int(raw_policy.get("duration_days", 0) or 0),
                "server_cache_hours": int(raw_policy.get("server_cache_hours", 0) or 0),
                "fail_closed": True,
            }
            # V2 Trial policy is capability-complete. Historical item allowlists
            # may remain in Firestore but are not projected into new grants.
            compatibility = stored.get("compatibility")
            if isinstance(compatibility, dict) and compatibility:
                policy["compatibility"] = compatibility
            return policy

        policy: Dict = {
            "schema": "core_trial_policy_v1",
            "enabled": True,
            "policy_source": "environment_fallback",
            "pipeline_runs_per_day": self.trial_pipeline_runs_per_day,
            "plugin_hours_per_day_per_plugin": self.trial_plugin_hours_per_day_per_plugin,
            "quota_scope": "entitlement_activation_local_day",
            "trial_seat_limit": 1,
            "fail_closed": True,
        }
        # Trial item allowlists are deprecated: Trial has full capability access.
        return policy

    def offline_projection(self, *, grant_ttl_seconds: int) -> Dict:
        # V1 never extends authority beyond the signed grant itself. A future
        # grace-mode contract may be introduced explicitly rather than treating
        # an expired grant as valid.
        effective_max = min(self.offline_max_seconds, max(0, int(grant_ttl_seconds)))
        if not self.offline_allowed:
            effective_max = 0
        return {
            "allowed": bool(self.offline_allowed and effective_max > 0),
            "max_seconds": effective_max,
            "requires_valid_grant": True,
        }
