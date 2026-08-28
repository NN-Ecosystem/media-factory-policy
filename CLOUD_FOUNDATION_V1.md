# Core Factory Cloud Foundation V1 — additive baseline

This patch intentionally preserves all existing endpoints (`/verify`, `/trial/resolve`, Owner, license creation, trial switch) and adds a parallel Cloud V1 path.

## New flow

`register email -> verify email -> user trial -> entitlement -> core registration -> signed access grant`

New Firestore collections: `cloud_users`, `cloud_user_emails`, `email_verifications`, `user_trials`, `entitlements`, `core_registrations`.

New endpoints:
- `POST /v1/cloud/register`
- `POST /v1/cloud/email/verify`
- `GET /v1/cloud/users/{user_id}/status`
- `POST /v1/cloud/cores/register`
- `POST /v1/cloud/access-grants`

## Compatibility

Legacy machine trial remains untouched in `machine_trials`. Existing license verification/token behavior remains untouched. Migration to the new AccessGate can therefore be done end-to-end later.

## Security / deployment notes

- Verification tokens are stored only as SHA-256 hashes.
- Set `CLOUD_DEV_EXPOSE_VERIFICATION_TOKEN=true` only for development/testing. Production must leave it false and connect an email-delivery adapter before customer rollout.
- Core registration requires proof of the verified email token; it returns `core_secret` only on first registration. Store it locally as a secret. Grant refresh requires this secret.
- Access grants reuse the existing RSA signer and are bound to both `user_id` and `core_id`.
- Default grant TTL is 12h (`CLOUD_ACCESS_GRANT_TTL_SECONDS=43200`) and is capped by entitlement expiry.
- Trial defaults to 14 days (`CLOUD_TRIAL_DAYS=14`) and starts at `email_verified_at`.
- Billing contracts are present but no payment provider is connected. Payment must later project Billing state into Entitlement; it must not unlock Core directly.

## Required next integration

Before public release, connect an email provider, add rate limiting/audit logging to public mutation endpoints, and integrate Local Core AccessGate verification of `core_access_grant_v1` in one coordinated end-to-end migration.

## Email verification delivery adapter

Cloud V1 now has an explicit email-delivery boundary.

- Default: `CLOUD_EMAIL_PROVIDER=disabled` — safe mode; no verification secret is emitted.
- DEV/TEST only: `CLOUD_EMAIL_PROVIDER=console` — the one-time token is written to the Render server log as `CLOUD_DEV_EMAIL_VERIFICATION ...`.
- `/v1/cloud/register` never needs to expose the token. Keep `CLOUD_DEV_EXPOSE_VERIFICATION_TOKEN=false` (or unset).
- A real provider should implement `EmailDeliveryAdapter.send_verification(...)`; registration/trial/entitlement logic does not change.

For current Render integration testing, temporarily set `CLOUD_EMAIL_PROVIDER=console`, deploy, register a fresh test email, copy the token from the Render log, then return the setting to `disabled` after testing. Never use the console adapter for customer production traffic.

## V1.1 hardening checkpoint

This additive hardening keeps all legacy routes and data intact while adding release-quality boundaries:

- structured Cloud error codes (`detail.code`, `detail.message`)
- append-only `audit_events` for Cloud account/core/grant transitions
- single-process rate-limit boundary for register/verify/core-register/grant endpoints
- `core_secret` remains hash-only in Firestore and is returned only on first Core registration
- reusable `GrantVerifier` for signature, issuer, expiry, subject/core binding and permission checks
- explicit account/core/entitlement status checks before grant issuance
- `billing_events` idempotency repository keyed by `(provider, provider_event_id)`
- console verification delivery is blocked when `CLOUD_ENV=production` unless explicitly overridden
- renamed verification lookup to `find_by_token()` while retaining a compatibility alias

### New optional environment values

```text
CLOUD_ENV=development|production
CLOUD_ALLOW_CONSOLE_EMAIL=false
CLOUD_REGISTER_RATE_LIMIT=10
CLOUD_VERIFY_RATE_LIMIT=20
CLOUD_CORE_REGISTER_RATE_LIMIT=20
CLOUD_GRANT_RATE_LIMIT=120
```

For the current test deployment, `CLOUD_EMAIL_PROVIDER=console` remains valid while `CLOUD_ENV` is unset/development. Before public registration, replace the console adapter with a real email provider and set `CLOUD_ENV=production`.

## P30A Cloud Access Policy Foundation (v1.9.0)

Access Grant V1 remains schema-compatible (`core_access_grant_v1`) and now adds signed policy projections for Local Core TrialGate integration.

New signed payload fields:

- `access.state` — canonical access state (`active` for an issued Core grant)
- `access.product` — currently `core`
- `access.plan` / `access.source` / `access.entitlement_id`
- `access.entitlement_expires_at` — authoritative product-access lifetime
- `access.grant_expires_at` — credential freshness boundary; equals top-level `expires_at`
- `offline.allowed`
- `offline.max_seconds`
- `offline.requires_valid_grant=true`

The distinction is intentional: **grant expiry is not trial expiry**. Local Core must refresh an expired grant when online; it must not label the Trial expired unless the entitlement itself is inactive/expired.

Permission projection is now entitlement-aware. Only an active `product=core` entitlement projects the Core permission set. An unrelated active entitlement must not unlock Core capabilities.

Offline V1 is conservative: offline use is allowed only while the cached signed grant itself remains valid. It never extends authority past grant expiry or entitlement expiry. Future grace semantics require an explicit new contract rather than accepting an expired grant.

Optional environment values:

```text
CLOUD_OFFLINE_ACCESS_ALLOWED=true
CLOUD_OFFLINE_MAX_SECONDS=43200
```

Usage quotas are intentionally not part of P30A. Billing/Trial remain sources of Entitlement; Entitlement is projected into the signed grant; Local Core consumes the signed policy.
