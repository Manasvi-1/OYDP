/** Secure cookies require HTTPS. Loopback HTTP demos and e2e must stay usable. */
export function cookieSecure(env = process.env) {
  if (env.OYDP_COOKIE_SECURE === '0') return false
  if (env.OYDP_COOKIE_SECURE === '1') return true
  return env.NODE_ENV === 'production'
}
