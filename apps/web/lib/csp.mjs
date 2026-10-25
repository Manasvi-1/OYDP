export function contentSecurityPolicy(nonce, development = false) {
  if (!/^[A-Za-z0-9+/]{24,}={0,2}$/.test(nonce)) throw new Error('Invalid CSP nonce');
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ''}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "connect-src 'self'", "img-src 'self' data:", "font-src 'self'",
    "frame-ancestors 'none'", "base-uri 'none'", "form-action 'self'", "object-src 'none'"
  ].join('; ');
}
