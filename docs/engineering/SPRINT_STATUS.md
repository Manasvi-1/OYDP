# Sprint status

**Sprint focus:** PR #38 CSP + runtime audit/source gates + T-NEXT-012 attribution wiring.  
**Date:** 2026-11-12.

## Goals

| Goal | State |
| --- | --- |
| Wire Next.js CSP middleware (AUD / presentation) | Done (PR #38) |
| Close OpenAPI AUD-001 drift | Done (`export_active_openapi.py --check`) |
| Migration 020 audit/source/assertion gates | Implemented + static tests; PG integration BLOCKED locally |
| T-NEXT-012 web attribution write/display | Done on PR #38 branch (API already had PUT) |
| Withdrawn-source conflicts for docs/reviews | Done (API 0.17.0) |
| Process-local rate limit + docs exposure posture | Done (honest non-distributed) |
| PostGIS IDOR / local PostGIS | **BLOCKED** (`T-NEXT-009`, no Docker) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- PR #38 `security/web-csp-and-repo-presentation` (do not merge without CI green + review).

## Carry-over

- Local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review; distributed rate limiting.
