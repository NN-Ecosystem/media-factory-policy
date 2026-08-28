# Core Factory Cloud — Distribution Gate V1

Cloud V1.8 adds a generic managed-runtime distribution gate without changing the legacy license/trial endpoints or Cloud Foundation account/grant contracts.

## Endpoints

- `POST /v1/cloud/distributions/resolve` — authenticates registered Core credentials + active entitlement, resolves approved release metadata, and returns a short-lived CloudGate URL.
- `GET /v1/cloud/distributions/download?ticket=...` — verifies the signed/expiring ticket and streams the approved upstream artifact. Core never receives permanent storage credentials or the backing URL in resolution metadata.

## Trusted metadata

Release configuration is `binary_distributions.json` (or `CLOUD_BINARY_DISTRIBUTIONS_FILE`). Schema remains `core_factory_binary_distributions_v1`. SHA256 is pinned in this trusted release metadata; the download response is never used as the trust root.

Use `binary_distributions.example.json` as the template. Do not deploy placeholders.

## Authorization

A distribution resolve requires verified active account, registered active Core, correct `core_secret`, and active entitlement. Grants now also project semantic permissions `runtime.distribution.resolve` and `runtime.distribution.download` for future policy convergence.

## Environment

- `CLOUD_BINARY_DISTRIBUTIONS_FILE` optional override
- `CLOUD_DISTRIBUTION_TICKET_TTL_SECONDS` default `600`
- `CLOUD_DISTRIBUTION_RESOLVE_RATE_LIMIT` default `120/hour`
- `CLOUD_DISTRIBUTION_UPSTREAM_TIMEOUT` default `60s`

## Release artifact workflow

Build `tesseract_windows_x64.zip` using Core's existing `scripts/build_tesseract_portable_distribution.py`, publish it at an approved HTTPS backing location, then commit the exact URL/SHA256 into Cloud `binary_distributions.json`. CloudGate remains generic; the artifact may later move behind object storage/CDN without changing Core/Engine contracts.

## V1.8.1 — Private GitHub Release storage adapter

CloudGate can now keep release binaries in a private GitHub repository without
exposing a GitHub credential to Local Core.

Required Render environment for `storage.kind=github_release`:

```text
GITHUB_RELEASE_TOKEN=<fine-grained token with Contents: Read for the release repo>
```

Trusted release metadata stores only immutable artifact identity, SHA256, size,
and the GitHub release locator (`owner/repo/tag/asset`). The token remains only
in server environment. Core receives a short-lived CloudGate download URL.

Current approved artifact:

```text
tesseract / 5.5.3.20260724 / windows-amd64
asset: tesseract_windows_x64.zip
size: 45981169
sha256: ebc734c54c50bd2a7e16bc09f4ad68675300d4244bee1ce37079de3e2253600c
```
