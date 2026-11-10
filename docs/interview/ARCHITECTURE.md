# Interview architecture note

## Active stack

- Web: `apps/web` (Next.js App Router, server actions, sealed httpOnly session)
- API: `apps/api` (FastAPI, OIDC access-token verification, MFA gates)
- DB: `infra/db` migrations on PostgreSQL public schema, role `oydp_app`, forced RLS
- Frozen reference: root `oydp/` + `migrations/` from PR #1 — not interchangeable

## Trust boundaries

- Browser never chooses `PROPERTY_API_BASE`
- Access token sealed with `SESSION_KEY` (AES-GCM), never stored in `localStorage`
- Tenant membership is provisioned out-of-band; UI cannot create memberships
- Document bytes encrypted; download requires API `scan_state=pass`
- Diligence notes are workspace text, not legal transactions

## Implemented vs planned

| Area | Status |
|---|---|
| Property create/read/share, claims, identifiers, reviews, documents, consent export | Executable in active API + workspace |
| Diligence requests/notes/close | Executable |
| Audit ledger + local outbox delivery | Executable; not independent immutable archive |
| Malware scanner | Absent; files remain quarantined |
| Engines E02, E04–E13 | Planned |
| Production IdP, MFA enrollment, public deployment | Not selected / not approved |

## Decision preview

Deterministic classification of first-page API signals into honest buckets. No model endpoint exists in this repository.
