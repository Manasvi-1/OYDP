import { createHash, randomBytes } from 'node:crypto'

export const OIDC_COOKIE = 'oydp_oidc'

function allowedHttp(url) {
  if (url.protocol === 'https:') return true
  return url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1')
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
  const apiBase = String(env.PROPERTY_API_BASE ?? 'http://127.0.0.1:8000').trim()
  if (!issuer && !clientId && !redirectUri) return null
  if (!issuer || !clientId || !redirectUri) return { ok: false, error: 'Sign-in configuration is incomplete' }
  let issuerUrl
  let redirectUrl
  let apiUrl
  try {
    issuerUrl = new URL(issuer)
    redirectUrl = new URL(redirectUri)
    apiUrl = new URL(apiBase)
  } catch {
    return { ok: false, error: 'Sign-in configuration is invalid' }
  }
  if (!allowedHttp(issuerUrl) || !allowedHttp(redirectUrl) || !allowedHttp(apiUrl)) {
    return { ok: false, error: 'Sign-in URLs must be https, or http on localhost' }
  }
  if (issuerUrl.username || issuerUrl.password || issuerUrl.search || issuerUrl.hash || redirectUrl.username || redirectUrl.search || redirectUrl.hash) {
    return { ok: false, error: 'Sign-in URLs cannot include credentials or a query' }
  }
  return {
    ok: true,
    issuer: issuerUrl.origin + issuerUrl.pathname.replace(/\/$/, ''),
    clientId,
    redirectUri: redirectUrl.origin + redirectUrl.pathname,
    apiBase: apiUrl.origin,
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

export function readUnverifiedStringClaim(token, name) {
  const parts = String(token ?? '').split('.')
  if (parts.length !== 3) return ''
  try {
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
    const value = payload[name]
    return typeof value === 'string' ? value : ''
  } catch {
    return ''
  }
}
