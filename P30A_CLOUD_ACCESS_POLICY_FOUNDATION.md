# Core Factory Cloud — P30A Access Policy Foundation

## Goal
Prepare the signed Cloud contract consumed by Local Core TrialGate without changing legacy License/Trial endpoints or the existing `core_access_grant_v1` schema identity.

## Authority chain

`Trial / Billing / Admin source -> Entitlement -> Cloud Access Policy -> Signed Access Grant -> Local Core AccessGate`

Trial, payment, or a provider must never directly unlock Core.

## Additive grant fields

```json
{
  "access": {
    "state": "active",
    "product": "core",
    "plan": "trial",
    "source": "trial",
    "entitlement_id": "...",
    "entitlement_expires_at": 0,
    "grant_expires_at": 0
  },
  "offline": {
    "allowed": true,
    "max_seconds": 43200,
    "requires_valid_grant": true
  }
}
```

`expires_at` at the grant root remains the signed grant expiry. `access.entitlement_expires_at` is product access lifetime. They are not equivalent.

## Permission projection
Only an active `product=core` entitlement projects Core permissions. A non-Core entitlement cannot accidentally produce `core.execute`, `engine.execute`, `node.access`, or runtime-distribution permissions.

## Offline V1
Offline capability use is permitted only inside the validity window of the last verified signed grant. P30A does not create an expired-grant grace mode.

## Deferred
Usage quotas, payment providers, complex RBAC, and offline-expired-grant grace are not implemented in P30A.
