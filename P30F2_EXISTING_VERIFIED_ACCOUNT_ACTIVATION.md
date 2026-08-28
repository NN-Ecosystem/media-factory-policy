# P30F.2 — Existing Verified Account Activation

A verified email address is not, by itself, an authentication credential for a fresh Core installation.

Cloud registration is now account-aware:

- New/unverified account → `trial_verification` challenge; Trial starts only after successful verification.
- Existing verified account on a fresh Core → `core_activation` confirmation challenge; existing Trial/Entitlement is reused and is never restarted or extended.
- Already commissioned Core with local `core_id + core_secret` → normal grant refresh path; no email challenge is required for routine startup.

`POST /v1/cloud/register` remains non-blocking. Email delivery is queued in the background. For an existing verified account it returns:

- `account_state=existing_verified`
- `verification_required=false`
- `activation_confirmation_required=true`
- `verification_purpose=core_activation`
- `trial_activation_required=false`

Security invariant: a fresh installation MUST NOT become active merely because the caller knows an already-verified email address. The onboarding session must be confirmed through the email activation challenge (or a future equivalent authenticated account session).

Verification of a `core_activation` challenge calls the same idempotent Trial/Entitlement machinery, so existing `trial.started_at` and `trial.expires_at` are preserved.
