# Decision log

Architecture and delivery decisions with rationale. Newest first.

## 2026-11-11 — Merge main into interview branch before expanding scope

**Decision:** Reconcile `feat/interview-demo-workspace` with `origin/main` before further feature work and before treating PR #22 as security-complete on its tip.  
**Why:** Tip lacked SF-008 and the IDOR suite already on main; file overlap with interview commits was empty, so merge was low-risk.  
**Rejected alternative:** Land PR #22 then open a follow-up security PR only — would leave the long-lived interview branch defective for local continuity.  
**Status:** Accepted; merge commit `ed7b5b7`.

## 2026-11-11 — Route MFA tests stub authorized_db only

**Decision:** Add HTTP-level MFA negative tests that keep real `require_mfa` / JWKS verification and stub only `authorized_db`.  
**Why:** Integration suites often override MFA true; unit `require_mfa` tests never hit FastAPI wiring.  
**Rejected alternative:** Fake end-to-end success without DB — forbidden. Stubbing authz for MFA-denial paths does not claim tenant isolation.  
**Status:** Accepted; `test_mfa_route_gates.py`.

## 2026-11-11 — Merge eligibility under conflicting AGENTS vs user directive

**Decision:** Prefer stricter safety: merge only when PR is not draft, CI green, migrations reviewed (none added this session), no known critical security defects, and branch protection/approvals satisfied. If protection is absent, still require CI green and explicit eligibility; do not bypass required reviews if GitHub later enables them.  
**Status:** Standing rule for this execution directive.

## Prior standing decisions (repo)

| Decision | Rationale |
| --- | --- |
| Active authority is `apps/api` + `infra/db` | PR #16 consolidation; reference `oydp/` frozen |
| `scripts/migrate.py` rejects root `migrations/` | Prevent accidental schema mix |
| Claims remain `unverified`; reviews `title_effect=none` | No title/government claims |
| Document scanner None → quarantine forever until infra | Fail-closed over fake pass |
| Modular monolith; 13 engines remain commitments | Blueprint / AGENTS.md |
