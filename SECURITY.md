# Security policy

## Supported versions

No production release is currently supported. This repository is pre-alpha.

## Reporting a vulnerability

Contact the repository owner through a private channel available on their GitHub profile or repository settings. Do not disclose exploit steps, credentials, private deeds, or personal data in public issues or pull requests.

## Scope

Do not conduct unauthorized testing against government portals, third-party providers, or production systems. Use only owned or explicitly authorized test infrastructure and synthetic fixtures.

## Security posture (honest)

Implemented controls in this checkout include OIDC access-token verification, MFA freshness gates on high-risk API routes, tenant membership checks, PostgreSQL RLS, fail-closed document quarantine, and a nonce-based Content-Security-Policy middleware on the web workspace.

These controls are not a certification. Live identity enrollment, malware scanning, session kill on membership revoke, external immutable audit, privacy deletion/restore, and independent security review remain incomplete or blocked. See [`docs/engineering/SECURITY_STATUS.md`](docs/engineering/SECURITY_STATUS.md) and [`docs/engineering/KNOWN_GAPS.md`](docs/engineering/KNOWN_GAPS.md).
