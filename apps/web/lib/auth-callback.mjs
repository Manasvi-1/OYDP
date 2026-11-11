import { encodeSession, sealJson, sessionKeyBytes, UUID, SESSION_COOKIE } from './contract.mjs'
import { OIDC_COOKIE, verifySignedJwt } from './oidc.mjs'

export const PENDING_AUTH_COOKIE = 'oydp_pending_auth'
export const PENDING_AAD = 'oydp-pending-auth'
const PENDING_TTL_SECONDS = 600
const SESSION_TTL_SECONDS = 60 * 60 * 8
const CONNECT_PATH = '/connect'

export const CONNECT_BRIDGE_HTML = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta http-equiv="refresh" content="0;url=/connect"><title>Continuing</title></head><body><a href="/connect">Continue</a></body></html>'

const MESSAGES = {
  unconfirmed: 'Sign-in could not be confirmed. Start again.',
  unavailable: 'Identity provider unavailable',
  redirected: 'Identity provider refused to answer directly',
  unusable: 'Identity provider did not return a usable access token',
  property: 'Property service did not accept this sign-in',
}

export function authCookieOptions({ secure, path, maxAge }) {
  return {
    httpOnly: true,
    sameSite: 'lax',
    secure: Boolean(secure),
    path,
    maxAge,
  }
}

export function oidcTransactionCookie(value, secure) {
  return {
    name: OIDC_COOKIE,
    value,
    options: authCookieOptions({ secure, path: '/callback', maxAge: 600 }),
  }
}

function configuredOrigin(redirectUri) {
  try {
    return new URL(redirectUri).origin
  } catch {
    return null
  }
}

export function callbackLocation(redirectUri, pathAndQuery) {
  const origin = configuredOrigin(redirectUri)
  if (!origin || typeof pathAndQuery !== 'string') return null
  if (!pathAndQuery.startsWith('/') || pathAndQuery.startsWith('//') || pathAndQuery.includes('\\')) return null
  if (/[\u0000-\u0020]/.test(pathAndQuery)) return null
  let url
  try {
    url = new URL(pathAndQuery, origin)
  } catch {
    return null
  }
  if (url.origin !== origin) return null
  return url.toString()
}

function clearCookie(name, path, secure) {
  return { name, value: '', options: authCookieOptions({ secure, path, maxAge: 0 }) }
}

function failureDecision(redirectUri, secure, reason) {
  const message = MESSAGES[reason] ?? MESSAGES.unconfirmed
  return {
    kind: 'redirect',
    location: callbackLocation(redirectUri, `/?error=${encodeURIComponent(message)}`),
    html: null,
    cookies: [
      clearCookie(OIDC_COOKIE, '/callback', secure),
      clearCookie(PENDING_AUTH_COOKIE, '/', secure),
    ],
  }
}

export function callbackFailure(redirectUri, secure, reason) {
  return failureDecision(redirectUri, secure, reason)
}

function confirmedPending(code, state, pending, now) {
  return Boolean(
    code &&
    state &&
    pending &&
    pending.v === 1 &&
    state === pending.state &&
    typeof pending.verifier === 'string' &&
    pending.verifier &&
    typeof pending.nonce === 'string' &&
    pending.nonce &&
    typeof pending.exp === 'number' &&
    pending.exp > now
  )
}

export function beginCallback({ redirectUri, requestUrl, now, code, state, pending, secure }) {
  let incoming = null
  try {
    incoming = new URL(requestUrl).origin
  } catch {
    incoming = null
  }
  if (!configuredOrigin(redirectUri) || incoming !== configuredOrigin(redirectUri)) {
    return { done: true, decision: failureDecision(redirectUri, secure, 'unconfirmed') }
  }
  if (!confirmedPending(code, state, pending, now)) {
    return { done: true, decision: failureDecision(redirectUri, secure, 'unconfirmed') }
  }
  return { done: false, next: 'exchange', verifier: pending.verifier }
}

/**
 * @param {{
 *   redirectUri: string,
 *   now: number,
 *   pending: Record<string, unknown> | null,
 *   secure: boolean,
 *   sessionKey?: string,
 *   issuer: string,
 *   audience: string,
 *   clientId: string,
 *   exchange: { ok?: boolean, accessToken?: string, idToken?: string },
 *   jwks: { keys?: unknown[] },
 *   propertyAccepted?: boolean,
 * }} input
 */
export function finishCallback({
  redirectUri,
  now,
  pending,
  secure,
  sessionKey,
  issuer,
  audience,
  clientId,
  exchange,
  jwks,
  propertyAccepted,
}) {
  if (!exchange?.ok || typeof exchange.accessToken !== 'string' || !exchange.accessToken || !sessionKeyBytes(sessionKey)) {
    return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
  }
  const accessCheck = verifySignedJwt(exchange.accessToken, {
    jwks,
    issuer,
    audience,
    now,
    typ: 'at+jwt',
  })
  if (!accessCheck.ok) return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
  const idToken = typeof exchange.idToken === 'string' ? exchange.idToken : ''
  if (idToken) {
    const idCheck = verifySignedJwt(idToken, {
      jwks,
      issuer,
      audience: clientId,
      nonce: pending.nonce,
      now,
      typ: 'JWT',
    })
    if (!idCheck.ok) return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
  } else if (accessCheck.payload.nonce !== pending.nonce) {
    return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
  }
  const tenantClaim = accessCheck.payload.tenant_id
  const tenantId = typeof tenantClaim === 'string' ? tenantClaim : ''
  const subject = typeof accessCheck.payload.sub === 'string' ? accessCheck.payload.sub : ''
  const remaining = Math.max(0, Math.floor(Number(accessCheck.payload.exp) - now))
  if (UUID.test(tenantId)) {
    if (propertyAccepted === undefined) {
      return { done: false, next: 'probe', tenantId, accessToken: exchange.accessToken }
    }
    if (!propertyAccepted) return { done: true, decision: failureDecision(redirectUri, secure, 'property') }
    let sessionValue
    try {
      sessionValue = encodeSession({ tenantId, accessToken: exchange.accessToken }, { key: sessionKey, now })
    } catch {
      return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
    }
    return {
      done: true,
      decision: {
        kind: 'redirect',
        location: callbackLocation(redirectUri, '/overview'),
        html: null,
        cookies: [
          clearCookie(OIDC_COOKIE, '/callback', secure),
          clearCookie(PENDING_AUTH_COOKIE, '/', secure),
          {
            name: SESSION_COOKIE,
            value: sessionValue,
            options: authCookieOptions({ secure, path: '/', maxAge: Math.min(SESSION_TTL_SECONDS, remaining) }),
          },
        ],
      },
    }
  }
  let pendingValue
  try {
    pendingValue = sealJson({
      v: 1,
      accessToken: exchange.accessToken,
      subject,
      exp: now + Math.min(PENDING_TTL_SECONDS, remaining),
    }, sessionKey, PENDING_AAD)
  } catch {
    return { done: true, decision: failureDecision(redirectUri, secure, 'unusable') }
  }
  return {
    done: true,
    decision: {
      kind: 'bridge',
      location: callbackLocation(redirectUri, CONNECT_PATH),
      html: CONNECT_BRIDGE_HTML,
      cookies: [
        clearCookie(OIDC_COOKIE, '/callback', secure),
        {
          name: PENDING_AUTH_COOKIE,
          value: pendingValue,
          options: authCookieOptions({
            secure,
            path: '/',
            maxAge: Math.min(PENDING_TTL_SECONDS, remaining),
          }),
        },
      ],
    },
  }
}
