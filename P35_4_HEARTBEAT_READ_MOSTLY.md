# P35.4 — Read-mostly Seat Heartbeat

Target: ~5K concurrent Personal Cores.

Behavior
- Authority heartbeat remains every 5 minutes (+/-30s jitter).
- Every heartbeat still validates Core/account/activation/plan authority.
- Activation lease telemetry is written only every 15 minutes.
- True seat transfer/revoke is still discovered on the next 5-minute heartbeat.
- First heartbeat after activation writes telemetry immediately.

Load effect
- HTTP heartbeat traffic: unchanged from P35.3 (~16.7 req/s at 5K Cores).
- Firestore lease writes: ~3x lower than P35.3.
- At 5K continuously-online Cores: average telemetry writes ~5.6/s instead of ~16.7/s.
- Most heartbeats avoid the second transactional activation read/write.

Security
- Non-write heartbeats remain authoritative because the already-loaded active activation
  is validated against user_id/core_id/lease_generation.
- When telemetry is due, the existing transaction re-validates the binding before write,
  so a concurrent seat transfer cannot be reclaimed by the old Core.
