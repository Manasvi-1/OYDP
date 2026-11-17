# Sprint status

**Sprint focus:** Merge PR #38 after portable-PG acceptance; continue unblocked security/E01.  
**Date:** 2026-11-12.

## Goals

| Goal | State |
| --- | --- |
| Wire Next.js CSP middleware (AUD / presentation) | Done (PR #38) |
| Close OpenAPI AUD-001 drift | Done (`export_active_openapi.py --check`) |
| Migration 020 audit/source/assertion gates | Implemented; portable PG **250 passed** |
| T-NEXT-011 web graph/conflicts | **VERIFIED** on main (PR #37) |
| T-NEXT-012 web attribution write/display | Done on PR #38 branch (API already had PUT) |
| Withdrawn-source conflicts for docs/reviews | Done (API 0.17.0) |
| Process-local rate limit + docs exposure posture | Done (honest non-distributed) |
| PostGIS IDOR / local PostGIS | **BLOCKED** (`T-NEXT-009`, no Docker) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- PR #38 `security/web-csp-and-repo-presentation` — CI green; portable PG acceptance done; merge when eligible.

## Carry-over

- Local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review; distributed rate limiting.
