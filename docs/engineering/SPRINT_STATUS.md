# Sprint status

**Sprint focus:** E01 evidence-conflict dispositions (non-title) API 0.19.0 + web disposition UI on PR #43. PR #41 is on main. Do not merge open docs/dependabot PRs unless asked.  
**Date:** 2026-11-26.

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
| Membership-revoke session posture | Done on main (PR #41). Live IdP revocation still blocked |
| Evidence conflict dispositions | TESTED (API 0.19.0 + web UI; migration 022; 273 PG + 52 web) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- None for dispositions — PR #43 merged to `main` @ `5c103b3`.

## Carry-over

- Property dedup candidates (no auto-merge); local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review; distributed rate limiting.
