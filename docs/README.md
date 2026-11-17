# OYDP documentation map

Use this index when navigating the repository. When a document disagrees with code, trust `AGENTS.md`, `apps/api`, `infra/db`, and Git history.

## Start here

| Doc | Purpose |
| --- | --- |
| [`../README.md`](../README.md) | Product posture, layout, local setup |
| [`../AGENTS.md`](../AGENTS.md) | Contributor and automation contract |
| [`../SECURITY.md`](../SECURITY.md) | Vulnerability disclosure |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | PR expectations |
| [`ENGINE_REGISTER.md`](ENGINE_REGISTER.md) | Honest status of the 13 engines |
| [`ROADMAP.md`](ROADMAP.md) | Near-term engineering horizons |

## Implementation truth

| Doc | Purpose |
| --- | --- |
| [`implementation/BUILD_STATUS.md`](implementation/BUILD_STATUS.md) | What is actually built |
| [`implementation/VERIFICATION_REGISTER.md`](implementation/VERIFICATION_REGISTER.md) | Verification evidence register |
| [`implementation/TRUSTED_EVIDENCE.md`](implementation/TRUSTED_EVIDENCE.md) | Evidence / export / graph contracts |
| [`implementation/IDENTITY_GATE.md`](implementation/IDENTITY_GATE.md) | OIDC / MFA gates |
| [`implementation/WEB_CSP.md`](implementation/WEB_CSP.md) | Workspace CSP middleware |
| [`implementation/PR1_RECONCILIATION.md`](implementation/PR1_RECONCILIATION.md) | Active vs frozen reference backends |
| [`implementation/PRODUCTION_READINESS.md`](implementation/PRODUCTION_READINESS.md) | Why this is not GA |

## Engineering session ledger

| Doc | Purpose |
| --- | --- |
| [`engineering/BUILD_LEDGER.md`](engineering/BUILD_LEDGER.md) | Append-only session ledger |
| [`engineering/KNOWN_GAPS.md`](engineering/KNOWN_GAPS.md) | Blocked and unfinished items |
| [`engineering/IMPLEMENTATION_STATUS.md`](engineering/IMPLEMENTATION_STATUS.md) | Labelled maturity snapshot |
| [`engineering/SECURITY_STATUS.md`](engineering/SECURITY_STATUS.md) | Security control inventory |
| [`engineering/RELEASE_READINESS.md`](engineering/RELEASE_READINESS.md) | Release gate checklist |

## Architecture, security, interview

| Doc | Purpose |
| --- | --- |
| [`architecture/README.md`](architecture/README.md) | Modular-monolith notes |
| [`security/README.md`](security/README.md) | Security doc entry |
| [`THREAT_MODEL.md`](THREAT_MODEL.md) | Threat model |
| [`interview/START_LOCAL.md`](interview/START_LOCAL.md) | Local demo path |
| [`reference/`](reference/) | Controlling blueprint extract |

## Authority rules

1. Active service: `apps/api` + `infra/db` (public schema, role `oydp_app`).
2. Frozen reference: root `oydp/` + `migrations/` (schema `oydp`, role `oydp_runtime`).
3. Do not claim title verification, government affiliation, guaranteed valuation, or production readiness without attributable evidence.
4. Prefer evidence labels from the master engineering standard: planned, UI prototype, static mockup, placeholder, generated source, executable implementation, integration-tested, production-hardened, independently reviewed.
