const NONCE = /^[A-Za-z0-9+/=_-]{8,200}$/

export function useProductionCsp(env = process.env) {
  return env.NODE_ENV === 'production'
}

export function contentSecurityPolicy(nonce, production) {
  if (typeof nonce !== 'string' || !NONCE.test(nonce)) {
    throw new Error('CSP nonce is missing')
  }
  const script = production
    ? `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`
    : `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'unsafe-eval'`
  // Style attributes are not covered by nonces; keep styles file-based only.
  return [
    "default-src 'self'",
    script,
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
}
