# Nonce-based workspace content security policy

Next.js 15 loads `apps/web/middleware.js` on each matched HTML request. That middleware creates a cryptographically random 32-byte nonce, replaces any caller-supplied `x-nonce` / `Content-Security-Policy` headers before rendering, and sets the same policy on the response. `apps/web/proxy.js` is only a compatibility re-export; it is not the framework entrypoint.

The root layout calls `connection()` so the render stays on a request boundary and can receive the middleware nonce. HTML responses stay `Cache-Control: no-store`. API forwarding retains its separate allowlisted server-side client and authorization behavior.

Production has no `unsafe-inline` or `unsafe-eval` script directive. Development explicitly permits eval for framework debugging. Scripts use `strict-dynamic`. Styles are file-based (`style-src 'self'`); React `style={{...}}` attributes are avoided so a real CSP does not break the workspace. Frames, objects, and foreign base URIs are denied. No HTTPS-upgrade directive is forced onto loopback development; private non-loopback operation still requires operator-provided HTTPS.

Changed surfaces: `apps/web/middleware.js`, `apps/web/proxy.js`, `lib/csp.mjs`, `lib/csp-apply.mjs`, `app/layout.tsx`, `tests/middleware.test.mjs`, `tests/csp.test.mjs`, and related CSS class cleanups. No API/schema contract or migrations changed.

Local validation belongs in `npm test`, `npm run typecheck`, and `npm run build` under `apps/web`. Browser acceptance for independent nonces and blocked untrusted scripts remains an e2e concern when the local stack is up. Final commit-linked CI, rather than source presence alone, determines acceptance.

Reference: https://nextjs.org/docs/app/guides/content-security-policy

Still pending: provider-backed browser login, provider MFA freshness, external security review, malware-scanned document delivery, and other product release gates. CSP is defense in depth and does not certify XSS absence or production readiness.
