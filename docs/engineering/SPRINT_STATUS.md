# Sprint status

**Sprint focus:** Foundation security continuity + interview workspace cookie handoff + engineering evidence ledger.  
**Date:** 2026-11-11.

## Goals

| Goal | State |
| --- | --- |
| Audit repository with evidence | Done |
| Publish engineering ledger docs | Done |
| Keep PR #22 cookie fix mergeable without regressing main security | Done (merged) |
| Add non-overridden MFA route negatives | Done (incl. documents) |
| Re-run native PG integration locally | Done via portable PG 16.15 @ 55432 (238 pass) |
| Claim→source evidence edge | Done (API 0.9.0 / PR #25) |
| Document↔claim/source attribution | Done (API 0.10.0 / PR #27) |
| Document↔identifier + export refs | In delivery (`017`, API 0.11.0) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- T-NEXT-005 document↔identifier attribution (`feat/document-identifier-attribution`, API 0.11.0).

## Done recently (main history)

- PR #17 MFA freshness; PR #19 SF-008 + IDOR; PR #18/#21 interview workspace; PR #20 README honesty.

## Carry-over

- Local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review.
