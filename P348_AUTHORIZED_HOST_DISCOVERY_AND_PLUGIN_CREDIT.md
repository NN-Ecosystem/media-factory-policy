# Cloud P34.8 — Authorized Host discovery + default Plugin credit

- Authenticated Core identity is authoritative for requester email.
- `authorized_hosts` discovery returns online Hosts whose ephemeral presence advertises the SHA-256 hash of that email.
- Cloud Fabric never receives/stores Host account plaintext emails in presence metadata.
- Presence remains in-memory only.
- Existing same-account host listing remains backward compatible.
- Default Cloud pricing remains authoritative: `plugin.run = 3 credits / 3600 seconds`.
- Item-specific pricing remains supported only when explicitly configured by authoritative Cloud policy.
