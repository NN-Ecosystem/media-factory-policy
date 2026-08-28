# P30L.4 — Core Entitlement Priority

Release priority:
1. legacy_license
2. manual
3. trial

Rules:
- Full License always beats Trial.
- When activating a device, same-machine reusable seat is preferred.
- Otherwise prefer an entitlement with a free seat within the same authority class.
- A lower-priority Trial/manual entitlement cannot win merely because it already has an active seat.

Expected account example:
legacy_license / enterprise / 10 seats / 0 active
manual / personal / 1 seat / 1 active
trial / trial / 1 seat / 1 active

=> effective entitlement = legacy_license / enterprise
=> activation allowed while seats remain.
