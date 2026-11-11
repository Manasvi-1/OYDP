/**
 * Compatibility shim. Next.js 15 only auto-loads `middleware.js`.
 * Prefer `middleware.js` / `lib/csp-apply.mjs` in new code and tests.
 */
export { middleware as proxy, config } from './middleware.js'
