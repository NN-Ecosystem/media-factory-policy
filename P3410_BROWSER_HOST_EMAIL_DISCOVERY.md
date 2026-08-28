# Cloud P34.10 — Browser Host-email discovery

Generic browser entry: `/v1/cloud/connect`.

The visitor enters the Host Core owner's email. Cloud hashes it in-memory, resolves the one online Host advertising the matching owner-email hash, then redirects to the existing stable Host relay shell. The Host shell remains the authority for visitor account email/password and Node permissions.

Cloud returns the same generic `HOST_NOT_AVAILABLE` for unknown/offline/ambiguous Host identities.

Default Plugin usage pricing remains 3 credits per 3600 seconds.
