# P34A Secure Activation Routing + Verified Seat Transfer

This is a cumulative Cloud patch over P33 Plan Policy Store.

Fixes the missing routing boundary that caused:
- `/v1/cloud/licenses/email/activate` to return 409 seat-limit before verified transfer;
- email + machine hash to remain a possible direct activation path in the P33 Cloud copy.

Final semantics:
1. Silent `/licenses/email/activate` requires SAME-account persisted `core_id + core_secret`.
2. Different account/Core or missing/stale credential returns confirmation-required; email knowledge is not proof.
3. Core falls back to existing onboarding/register confirmation flow.
4. After fresh `core_activation` / `license_recovery` email proof, `complete_onboarding()` may transfer a one-seat entitlement.
5. Previous Core registration is retained as `replaced`.
6. Multi-seat plans are not auto-evicted.
7. P33 signed usage-policy behavior remains intact.

Deploy the `server/` files to Cloud. Apply `CORE/` files only if the target Core does not
already contain the P33 Secure Account Rebind patch.
