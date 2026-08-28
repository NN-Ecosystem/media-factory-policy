# Cloud P34.11 — Core-to-Core Remote Node CORS Hotfix

## Symptom
- Browser Host portal: Node UI works.
- Connected Personal Core: the same Node client bundle renders, then reports `Failed to fetch`.

## Root cause
The browser Host portal is same-origin with the Cloud public Host relay. A Node client bundle embedded inside Personal Core is cross-origin: its browser Origin is the local Streamlit loopback URL. Cloud global CORS allowed only the GitHub Pages landing origin, so the browser blocked relay API calls before they reached the Host.

## Fix
Cloud CORS now additionally accepts only loopback Personal Core web origins:
- `http(s)://localhost:<dynamic-port>`
- `http(s)://127.0.0.1:<dynamic-port>`
- `http(s)://[::1]:<dynamic-port>`

No wildcard origin is enabled. Existing GitHub Pages origins remain environment-controlled by `CLOUD_PUBLIC_CORS_ORIGINS`.

Authorization is unchanged:
- Cloud relay token / route
- service-scoped Host UI bearer token
- Host account state
- Node Service assignment + permissions

## Freeze effect
This is a transport regression hotfix and is valid for the Core 3.4.11 freeze line. It does not change Node storage, schemas, billing, or runtime contracts.
