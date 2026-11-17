# Sprint status

**Sprint focus:** Continue unblocked security/E01 after PR #38 merge.  
**Date:** 2026-11-17.

## Goals

| Goal | State |
| --- | --- |
| Wire Next.js CSP middleware (AUD / presentation) | **MERGED** (PR #38 @ `d960308`) |
| Close OpenAPI AUD-001 drift | Done (`export_active_openapi.py --check`) |
| Migration 020 audit/source/assertion gates | Implemented; portable PG **250 passed** |
| T-NEXT-011 web graph/conflicts | **VERIFIED** on main (PR #37) |
| T-NEXT-012 web attribution write/display | **VERIFIED** on main (PR #38) |
| Withdrawn-source conflicts for docs/reviews | Done (API 0.17.0) |
| Process-local rate limit + docs exposure posture | Done (honest non-distributed) |
| pip-audit CVE-2026-126360 (`opentelemetry-api`) | Fixed on PR #38 tip `27fc8cd` → `1.45.2` |
| PostGIS IDOR / local PostGIS | **BLOCKED** (`T-NEXT-009`, no Docker) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- None for PR #38 (merged). Next: membership-revoke session posture / E01 depth; skip T-NEXT-009.

## Carry-over

- Local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review; distributed rate limiting.
