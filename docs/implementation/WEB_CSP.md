# Nonce-based workspace content security policy

The Next.js request proxy creates a cryptographically random 32-byte nonce for each HTML request and replaces caller-supplied nonce/CSP headers before rendering. It sets the same policy on the response. The root layout waits for a request with `connection()` so the framework can attach the nonce to generated scripts/styles. HTML stays uncached. API forwarding retains its separate allowlisted proxy and authorization behavior.

Production has no unsafe-inline or unsafe-eval directive. Development explicitly permits eval for framework debugging. Scripts use strict-dynamic; style sources require the nonce or same origin. Frames, objects and base elements are denied. No HTTPS-upgrade directive is forced onto loopback development; private non-loopback operation still requires operator-provided HTTPS.

Changed files: apps/web/proxy.js, lib/csp.mjs, next.config.mjs, app/layout.js, tests/csp.test.mjs, e2e/security.spec.mjs and README.md. No API/schema contract or migrations changed.

Local validation: ten Node tests passed; Next production build passed with dynamic HTML routes; production HTTP checks passed for independent 256-bit nonces, matching script attributes, replaced forged headers and no-store. Browser acceptance asserts blocked nonce-less/replayed-nonce script injection plus the existing real API/PostgreSQL property, grant, revocation and denial journey. Final commit-linked CI, rather than source presence, determines browser acceptance.

Reference: https://nextjs.org/docs/app/guides/content-security-policy

Still pending: provider-backed browser login, provider MFA freshness, external security review, secure documents and other product release gates. CSP is defense in depth and does not certify XSS absence or production readiness.
