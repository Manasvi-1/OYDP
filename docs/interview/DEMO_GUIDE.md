# OYDP interview demonstration guide

Property Intelligence Workspace on the active `apps/web` + `apps/api` + `infra/db` stack. Pre-alpha. Not a government authority. Not production-approved.

## What you can show

1. Authenticated shell with Overview, Properties, Evidence, Diligence, Activity, Engines, Decision preview, Settings.
2. Real property create/list/detail against PostgreSQL with tenant isolation.
3. Unverified claims, identifiers, quarantined documents, diligence requests/notes, delivered audit timeline.
4. Honest 13-engine directory and a deterministic decision preview (no fake AI title verification).

## What you must not claim

- All 13 engines are complete.
- Title, ownership, survey, or approvals are verified.
- Documents are malware-free unless a real scanner returned `pass`.
- Local audit outbox is an immutable archive.

## Five-minute presentation flow

1. Open `http://127.0.0.1:3000`, sign in, enter the provisioned tenant UUID.
2. Overview: page-scoped counts only; open a synthetic property.
3. Property detail tabs: Claims, Documents (quarantined), Diligence open/note/close, Audit.
4. Engine directory: show Implemented / Partially implemented / Planned labels.
5. Decision preview: show deterministic buckets and the “no model endpoint” notice.

## Ten-minute technical walkthrough

1. Active service boundary: `apps/api` + `infra/db` public schema; root `oydp/` + `migrations/` is frozen reference.
2. Auth: OIDC access-token profile (`at+jwt`), MFA gates on writes, encrypted httpOnly session cookie (`SESSION_KEY`).
3. Tenant membership and RLS; cross-tenant reads return empty/404.
4. Documents encrypted at rest; absent scanner keeps `quarantined`.
5. Diligence is workspace commentary, not a transaction product.
6. Tests: `apps/web` unit/typecheck/build; API pytest; optional Playwright against disposable DB.

## Likely interview Q&A

**Q: Is title verified?**  
A: No. Claims stay `unverified`. Reviews have explicit non-title effect.

**Q: Why are documents not downloadable?**  
A: Upload quarantine is intentional. Without a scanner adapter, `scan_state` stays `quarantined` and content download is blocked.

**Q: Are all 13 engines live?**  
A: No. E01 foundations and bounded E03 diligence exist. The rest are planned launch commitments.

**Q: Can I bypass tenant checks in the browser?**  
A: No. The browser never chooses the API origin; authorization is enforced server-side with RLS.

## Local URLs

- Web: `http://127.0.0.1:3000`
- API health: `http://127.0.0.1:8000/healthz`
- Dev OIDC (optional): `http://127.0.0.1:9000`
