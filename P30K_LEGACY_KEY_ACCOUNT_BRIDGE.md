# Core Factory Cloud — P30K Legacy License Key -> Account Bridge

## Goal
Link an existing Local/Legacy License Key (1/N devices) to one verified Cloud account
without resetting expiry or multiplying its device allowance.

## Invariant
A 5-device key must remain a 5-device right after linking, NOT:
5 legacy devices + 5 account devices.

## Migration behavior
- one key can link to exactly one account
- account entitlement inherits plan, expiry and seat_limit
- seat_limit = max(device_limit, existing bound machine count, 1)
- existing `machine_hashes` are imported as occupied `legacy_reserved` activation seats
- existing local-bound machines remain valid for compatibility
- after link, NEW local machine binding is frozen
- new devices must use Account/Entitlement activation
- when an imported machine commissions a Cloud Core, its reserved seat is adopted by that Core
- legacy key is not deleted or revoked

## Admin API
POST /v1/cloud/admin/licenses/legacy/link-account
Payload:
- email
- license_key

Owner authentication remains unchanged.

## Trial / Owner
No Trial switch or Owner behavior is changed by P30K.
