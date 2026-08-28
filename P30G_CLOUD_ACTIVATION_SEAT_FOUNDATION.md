# Core Factory Cloud — P30G Activation Seat Foundation

## Goal
Close multi-Core Trial activation at Cloud authority level.

Verified Account -> Core Entitlement -> Activation Seat -> Core Registration -> Signed Grant

## Rules
- Existing/new Trial Core entitlement defaults to seat_limit=1.
- Same account + same machine reuses the existing seat.
- New machine with no available seat => ACTIVATION_SEAT_LIMIT_REACHED.
- Allocation is transactional using deterministic entitlement seat documents.
- Core registration persists activation_id + entitlement_id.
- Signed grant issuance requires an active activation and carries activation metadata.
- Pre-P30G registered Core is migration-safe: first valid grant refresh backfills its seat.
- If historical duplicate Cores already exist under a one-seat account, only the first successful seat backfill remains authorized.

## Next
P30H adds safe credential rotation/recovery for reinstall on the same bound machine.
