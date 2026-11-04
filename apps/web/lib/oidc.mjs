import { createHash, createPublicKey, randomBytes, timingSafeEqual, verify } from 'node:crypto'

function parsed(value) {
  try {
    return new URL(value)
  } catch {
    return null
  }
}

export function endpointAllowed(value, devFlag) {
  const url = parsed(value)
  if (!url || url.username || url.password || url.hash || url.search || !url.hostname) return false
  if (url.protocol === 'https:') return true
  const host = url.hostname.toLowerCase().replace(/\.$/, '')
  return url.protocol === 'http:' && devFlag === '1' && (host === 'localhost' || host === '127.0.0.1')
}

export function oidcConfig(env) {
  const issuer = String(env.OIDC_ISSUER || '')
  const clientId = String(env.OIDC_CLIENT_ID || '')
  const redirectUri = String(env.OIDC_REDIRECT_URI || '')
  const audience = String(env.OIDC_AUDIENCE || '')
  const devFlag = String(env.OYDP_OIDC_DEV_HTTP || '')
  if (!endpointAllowed(issuer, devFlag) || !endpointAllowed(redirectUri, devFlag)) return null
  if (!clientId || clientId.length > 200 || !audience || audience.length > 200) return null
  return { issuer: issuer.replace(/\/$/, ''), clientId, redirectUri, audience }
}

export function discoveryUrl(issuer) {
  return issuer.replace(/\/$/, '') + '/.well-known/openid-configuration'
}

export function pkceChallenge() {
  const verifier = randomBytes(32).toString('base64url')
  const challenge = createHash('sha256').update(verifier).digest('base64url')
  return {
    state: randomBytes(24).toString('base64url'),
    nonce: randomBytes(16).toString('base64url'),
    verifier,
    challenge,
  }
}

export function sameState(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string' || left.length < 16 || left.length !== right.length) return false
  return timingSafeEqual(Buffer.from(left), Buffer.from(right))
}

export function endpointsFromDiscovery(document, issuer) {
  if (!document || document.issuer !== issuer) return null
  const names = ['authorization_endpoint', 'token_endpoint', 'jwks_uri']
  const endpoints = {}
  for (const name of names) {
    const value = document[name]
    if (typeof value !== 'string') return null
    const url = parsed(value)
    const expected = parsed(issuer)
    if (!url || !expected || url.origin !== expected.origin || url.username || url.password || url.hash || url.search) return null
    endpoints[name] = value
  }
  return {
    authorization: endpoints.authorization_endpoint,
    token: endpoints.token_endpoint,
    jwks: endpoints.jwks_uri,
  }
}

export function authorizeUrl(endpoint, { clientId, redirectUri, audience, state, nonce, challenge }) {
  const url = new URL(endpoint)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', clientId)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('scope', 'openid')
  url.searchParams.set('state', state)
  url.searchParams.set('nonce', nonce)
  url.searchParams.set('code_challenge', challenge)
  url.searchParams.set('code_challenge_method', 'S256')
  url.searchParams.set('resource', audience)
  return url.toString()
}

export function accessTokenFromResponse(payload) {
  if (!payload || typeof payload !== 'object') return null
  if (String(payload.token_type || '').toLowerCase() !== 'bearer') return null
  const token = payload.access_token
  if (typeof token !== 'string' || token.length < 20 || token.length > 12000 || /\s/.test(token)) return null
  return token
}

function segment(value) {
  return JSON.parse(Buffer.from(value, 'base64url').toString('utf8'))
}

export function verifyAccessToken(token, jwks, { issuer, audience, now = Math.floor(Date.now() / 1000) }) {
  if (typeof token !== 'string' || token.split('.').length !== 3) throw new Error('rejected')
  const [h64, p64, s64] = token.split('.')
  const header = segment(h64)
  if (header.alg !== 'RS256' || header.typ !== 'at+jwt' || typeof header.kid !== 'string' || header.crit) throw new Error('rejected')
  const keys = jwks && Array.isArray(jwks.keys) ? jwks.keys : []
  const jwk = keys.find((key) => key && key.kid === header.kid && key.kty === 'RSA' && (key.alg == null || key.alg === 'RS256'))
  if (!jwk) throw new Error('rejected')
  const key = createPublicKey({ key: jwk, format: 'jwk' })
  const signatureOk = verify('RSA-SHA256', Buffer.from(`${h64}.${p64}`), key, Buffer.from(s64, 'base64url'))
  if (!signatureOk) throw new Error('rejected')
  const claims = segment(p64)
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (claims.iss !== issuer || !audiences.includes(audience)) throw new Error('rejected')
  if (typeof claims.exp !== 'number' || claims.exp <= now) throw new Error('rejected')
  if (typeof claims.iat !== 'number' || claims.iat > now + 60) throw new Error('rejected')
  if (typeof claims.sub !== 'string' || claims.sub.trim() === '' || claims.sub.length > 255) throw new Error('rejected')
  if (claims.amr != null && (!Array.isArray(claims.amr) || claims.amr.some((item) => typeof item !== 'string'))) throw new Error('rejected')
  return { sub: claims.sub, exp: claims.exp, amr: claims.amr || [] }
}

export function idTokenNonceMatches(idToken, nonce) {
  try {
    const [, payload] = String(idToken).split('.')
    return segment(payload).nonce === nonce
  } catch {
    return false
  }
}
