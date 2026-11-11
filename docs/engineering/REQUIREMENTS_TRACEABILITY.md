# Requirements traceability

Source hierarchy: controlled blueprint extract → 13-engine specification → architecture/roadmap → code/migrations/tests. Design text alone never proves completion.

Companion: `docs/implementation/TRACEABILITY.md` (historical). This file is the engineering ledger view as of 2026-11-11.

| Requirement | Implementation | Tests / evidence | Status |
| --- | --- | --- | --- |
| Modular monolith, 13 engines retained as commitments | `docs/ENGINE_REGISTER.md`; web Engines page Planned disclosure | Doc + UI honesty | E01 partial; others NOT_STARTED |
| Property identity private create/read | `apps/api` properties routes; `infra/db/001`,`006` | unit + CI integration | TESTED / CI VERIFIED |
| Tenant membership from DB, not client | `authorized_db` + `tenant_memberships` | CI RLS/integration | CI VERIFIED |
| PostgreSQL RLS / `oydp_app` | `infra/db/*`; `scripts/migrate.py` | CI database-security | CI VERIFIED; local BLOCKED |
| Read/write grants, revoke, expiry | SECURITY DEFINER grant functions | CI integration | CI VERIFIED |
| Unverified attributed claims | claim routes + `007` | CI + OpenAPI `unverified` const | TESTED / CI |
| MFA on high-risk mutations | `require_mfa` + route Depends | `test_auth.py`, `test_mfa_route_gates.py` | TESTED |
| MFA freshness `auth_time` | `auth.py` default 900s | unit + route gates | TESTED |
| Reject freshness-disable outside loopback | SF-008 `assert_mfa_configuration` | unit + route 503 | TESTED |
| Cross-tenant IDOR non-disclosure | `test_z_cross_tenant_idor.py` | CI Active database security | CI VERIFIED; local BLOCKED |
| Document quarantine + encryption | `documents.py`, `010` | unit + CI | TESTED / CI |
| Malware scanner before download | fail-closed gate; adapter None | unit asserts scanner None | BLOCKED (prod scanner) |
| Consent-gated export | consents + export authorize | CI history | CI VERIFIED |
| Audit outbox / append ledger | `013`, audit routes | CI | CI VERIFIED; external WORM NOT_STARTED |
| Diligence requests/notes | `014`, request routes | CI | TESTED (bounded E03) |
| Authenticated web workspace | `apps/web` | web CI; e2e scripts | partial TESTED |
| Loopback OIDC cookie handoff | callback `NextResponse` cookies | PR #22 web CI | TESTED (CI) |
| No title / government / valuation claims | OpenAPI consts; notices | contract tests | TESTED |
| Active vs reference backend separation | `test_canonical_authority.py`; migrate reject | unit | TESTED |
| E02 AI advisor | — | — | NOT_STARTED |
| E04–E13 product workflows | — | — | NOT_STARTED |
| Live managed IdP enrollment | realm file + verify script | script exits BLOCKED without Docker | BLOCKED |
| Privacy deletion/export/restore GA | — | — | NOT_STARTED |
| Independent security review | — | — | NOT_STARTED |
