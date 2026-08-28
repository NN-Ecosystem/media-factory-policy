# Core Factory Cloud — P30J Multi-device Seat Management

## Goal
Manage 1/N Core device seats for account-based entitlements.

## Added capabilities
- list all seats for an entitlement
- account-level seat overview
- deactivate an active seat
- trial seat reset is owner/admin only
- paid/manual entitlements can release seats explicitly
- released seats become available to the next valid activation

## Admin API
POST /v1/cloud/admin/entitlements/seats
POST /v1/cloud/admin/entitlements/seats/deactivate
POST /v1/cloud/admin/accounts/seat-overview

All routes require Owner credentials.

## Policy
Trial:
- default seat_limit = 1
- no self-service transfer in this tranche
- only owner/admin may reset/deactivate the seat

Paid/manual:
- seat_limit comes from entitlement
- admin may deactivate a device seat
- a new device may consume the newly-free seat on next activation

## Important runtime behavior
A deactivated Core will stop receiving valid Cloud grants once its cached grant expires
or when it next refreshes against Cloud authority.

Seat transfer is represented as:
1. deactivate old seat
2. activate new device into the free seat

No Core/device identity is rewritten in place.
