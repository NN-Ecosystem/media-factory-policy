# Core Factory Cloud — P30H Same-device Credential Recovery

## Goal
A reinstall or lost local `cloud_identity.dat` on the already-bound machine must
recover the existing Core identity instead of consuming another seat.

## Flow
Email confirmation / verified onboarding
-> resolve existing account entitlement
-> same machine activation seat
-> existing Core registration
-> rotate `core_secret`
-> issue fresh signed grant
-> return existing Core identity

## Security
Recovery requires ALL of:
- verified onboarding session
- active account
- active Core entitlement
- same user_id
- same machine_hash
- same activation_id
- same core_id

Different machine is denied. P30H does not implement seat transfer.

## Important
The old secret is never replayed; it is replaced atomically with a newly-generated secret.
Audit event: `cloud.core.credential_rotated`.
