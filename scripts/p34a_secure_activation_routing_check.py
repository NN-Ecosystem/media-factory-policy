from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
app=(root/"server/app.py").read_text(encoding="utf-8")
svc=(root/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
act=(root/"server/repositories/activation_repository.py").read_text(encoding="utf-8")
core=(root/"server/repositories/core_repository.py").read_text(encoding="utf-8")
client=(root/"CORE/services/cloud_onboarding_client.py").read_text(encoding="utf-8")
for text in (app,svc,act,core,client): ast.parse(text)

# /email/activate must require secret proof contract.
for name in ("current_user_id","current_core_id","current_core_secret"):
    assert name in app
    assert name in svc
assert "self.cores.verify_secret(current_core_id, current_core_secret)" in svc
assert "ACTIVATION_PROOF_REQUIRED" in svc
assert "ACCOUNT_SWITCH_CONFIRMATION_REQUIRED" in svc

# Client only sends proof for the same persisted account.
assert 'persisted_email == requested_email' in client
assert '"current_core_secret": identity["core_secret"]' in client

# Verified onboarding owns transfer semantics.
assert "def _reserve_after_verified_confirmation" in svc
assert 'purpose not in {"core_activation", "license_recovery"}' in svc
assert "transfer_single_seat" in svc
assert "seat_limit != 1" in svc
assert "def transfer_single_seat" in act
assert "def mark_replaced" in core
assert '"status": "replaced"' in core

# P33 plan policy remains intact.
assert "usage_policy_projection" in svc
assert "canonical_plan(access.get(\"plan\"))" in svc
assert "plan_policy_repo" in app
print("P34A SECURE ACTIVATION ROUTING + SEAT TRANSFER: PASSED")
