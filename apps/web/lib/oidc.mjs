import { createHash, createPublicKey, createVerify, randomBytes } from 'node:crypto'
import { configuredApiBase, configuredJwksUrl } from './origin.mjs'

export const OIDC_COOKIE = 'oydp_oidc'
const OIDC_AAD = 'oydp-oidc'

function allowedHttp(url) {
  if (url.protocol === 'https:') return true
  return url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1')
}

function cleanUrl(raw) {
  let url
  try {
    url = new URL(raw)
  } catch {
    return null
  }
  if (!allowedHttp(url) || url.username || url.password || url.search || url.hash) return null
  return url
}

export function randomUrlToken(bytes = 32) {
  return randomBytes(bytes).toString('base64url')
}

export function codeChallenge(verifier) {
  return createHash('sha256').update(verifier).digest('base64url')
}

export function oidcConfig(env) {
  const issuer = String(env.OIDC_ISSUER ?? '').trim().replace(/\/$/, '')
  const clientId = String(env.OIDC_CLIENT_ID ?? '').trim()
  const redirectUri = String(env.OIDC_REDIRECT_URI ?? '').trim()
  const audience = String(env.OIDC_AUDIENCE ?? '').trim()
  const signInUnset = !issuer && !clientId && !redirectUri && !audience && !String(env.OIDC_JWKS_URL ?? '').trim()
  if (signInUnset) return null
  const api = configuredApiBase(env)
  const jwks = configuredJwksUrl(env)
  if (!issuer || !clientId || !redirectUri || !audience || !api.ok || !jwks.ok) {
    return { ok: false, error: 'Sign-in configuration is incomplete' }
  }
  if (audience.length > 200 || audience.includes(' ')) return { ok: false, error: 'Sign-in configuration is invalid' }
  const issuerUrl = cleanUrl(issuer)
  const redirectUrl = cleanUrl(redirectUri)
  if (!issuerUrl || !redirectUrl) return { ok: false, error: 'Sign-in URLs must be https, or http on localhost' }
  return {
    ok: true,
    issuer: issuerUrl.origin + issuerUrl.pathname.replace(/\/$/, ''),
    clientId,
    redirectUri: redirectUrl.origin + redirectUrl.pathname,
    apiBase: api.origin,
    jwksUrl: jwks.url,
    audience,
  }
}

export function authorizeRequest(config, pending) {
  const url = new URL(`${config.issuer}/protocol/openid-connect/auth`)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', config.clientId)
  url.searchParams.set('redirect_uri', config.redirectUri)
  url.searchParams.set('scope', 'openid')
  url.searchParams.set('state', pending.state)
  url.searchParams.set('nonce', pending.nonce)
  url.searchParams.set('code_challenge', codeChallenge(pending.verifier))
  url.searchParams.set('code_challenge_method', 'S256')
  return url
}

export function tokenEndpoint(config) {
  return `${config.issuer}/protocol/openid-connect/token`
}

export function verifySignedJwt(token, options) {
  const parts = String(token ?? '').split('.')
  if (parts.length !== 3 || parts.some((part) => !part)) return { ok: false, error: 'Malformed token' }
  let header
  let payload
  try {
    header = JSON.parse(Buffer.from(parts[0], 'base64url').toString('utf8'))
    payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
  } catch {
    return { ok: false, error: 'Malformed token' }
  }
  if (header.alg !== 'RS256' || header.crit || header.jku || header.x5u || typeof header.kid !== 'string' || !header.kid) {
    return { ok: false, error: 'Unsupported token header' }
  }
  if (header.typ !== options.typ) return { ok: false, error: 'Unsupported token type' }
  const jwk = (options.jwks?.keys ?? []).find((key) => key && key.kty === 'RSA' && key.kid === header.kid && key.use !== 'enc')
  if (!jwk || (jwk.alg && jwk.alg !== 'RS256')) return { ok: false, error: 'Unknown signing key' }
  let verified = false
  try {
    const key = createPublicKey({ key: jwk, format: 'jwk' })
    const verifier = createVerify('RSA-SHA256')
    verifier.update(`${parts[0]}.${parts[1]}`)
    verified = verifier.verify(key, Buffer.from(parts[2], 'base64url'))
  } catch {
    verified = false
  }
  if (!verified) return { ok: false, error: 'Invalid token signature' }
  if (payload.iss !== options.issuer) return { ok: false, error: 'Invalid token issuer' }
  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud]
  if (!audiences.includes(options.audience)) return { ok: false, error: 'Invalid token audience' }
  if (typeof payload.exp !== 'number' || payload.exp <= options.now) return { ok: false, error: 'Expired token' }
  if (typeof payload.sub !== 'string' || !payload.sub.trim() || payload.sub.length > 255) {
    return { ok: false, error: 'Invalid token subject' }
  }
  if (options.nonce !== undefined && payload.nonce !== options.nonce) return { ok: false, error: 'Invalid token nonce' }
  return { ok: true, payload }
}

export async function fetchJwks(url) {
  const response = await fetch(url, { redirect: 'manual', cache: 'no-store', signal: AbortSignal.timeout(8000) })
  if (response.status >= 300 && response.status < 400) {
    throw new Error('Identity provider refused to answer directly')
  }
  if (!response.ok) throw new Error('Identity provider unavailable')
  const body = await response.json()
  if (!body || !Array.isArray(body.keys)) throw new Error('Identity provider keys are incomplete')
  return body
}

export { OIDC_AAD }
