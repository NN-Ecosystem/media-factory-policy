# P35.3 — 5-minute Seat Heartbeat Optimization

- Core heartbeat: 300s, jitter ±30s.
- First startup heartbeat remains immediate/early.
- Cloud seat lease default: 660s.
- Reuses already-loaded Core registration for secret verification.
- Queries active entitlements once per heartbeat and reuses the result.
- Plan Policy has a 60s in-process cache shared by all Cores on the server.
- Expected heartbeat HTTP/write load: ~80% lower than 60s cadence.
- Revocation/Trial-switch propagation: normally <=5 min, worst-case ~6 min with policy cache.
