# Core Factory Cloud — P30I Manual Email License Foundation

## Goal
Create new licenses by verified Cloud account/email instead of issuing new local license keys.

## Canonical flow
Owner/Admin
-> verified account email
-> immutable user_id
-> manual entitlement
-> seat_limit
-> activation seats
-> signed Core grant

## Added admin API
POST /v1/cloud/admin/entitlements/manual

Owner authentication uses the existing Owner credentials in request headers:
- X-Owner-Username
- X-Owner-Password

Payload supports:
- email
- product
- plan
- seat_limit
- starts_at
- expires_at OR duration_days
- source_id

Also added:
POST /v1/cloud/admin/accounts/license-status

## Rules
- Account must already exist and email must be verified.
- Manual license does NOT create a legacy/local license key.
- Default source_id is owner:<product>, producing one canonical owner-managed entitlement per account/product.
- Core seat_limit feeds the P30G Activation Seat authority directly.
- seat_limit cannot be reduced below the number of currently active Core seats.
- Manual entitlement outranks Trial in the existing Core entitlement selector.

## Migration
Legacy key issuance remains available only for compatibility while account-based licensing is adopted.
Future P30M License Management Plugin should call these Cloud Admin APIs instead of mutating Firestore directly.
