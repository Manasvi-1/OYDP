import assert from 'node:assert/strict'
import { createSign, generateKeyPairSync, randomBytes } from 'node:crypto'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  beginCallback,
  callbackFailure,
  callbackLocation,
  CONNECT_BRIDGE_HTML,
  finishCallback,
  oidcTransactionCookie,
  PENDING_AAD,
  PENDING_AUTH_COOKIE,
} from './auth-callback.mjs'
import { decodeSession, openJson, SESSION_COOKIE } from './contract.mjs'
import { OIDC_COOKIE } from './oidc.mjs'

const redirectUri = 'http://127.0.0.1:3000/callback'
const issuer = 'http://127.0.0.1:9000'
const now = 1_700_000_000
const sessionKey = randomBytes(32).toString('base64url')
const tenantId = '11111111-1111-4111-8111-111111111111'
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 })
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'callback-1', alg: 'RS256', use: 'sig' }
const jwks = { keys: [jwk] }

function signJwt(payload, header = {}) {
  const encodedHeader = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'callback-1', ...header })).toString('base64url')
  const encodedPayload = Buffer.from(JSON.stringify(payload)).toString('base64url')
  const signer = createSign('RSA-SHA256')
  signer.update(`${encodedHeader}.${encodedPayload}`)
  return `${encodedHeader}.${encodedPayload}.${signer.sign(privateKey).toString('base64url')}`
}

function accessToken(overrides = {}) {
  return signJwt({
    iss: issuer,
    aud: 'oydp-api',
    sub: 'alice',
    exp: now + 90,
    nonce: 'nonce-1',
    ...overrides,
  }, { typ: 'at+jwt' })
}

function pending(overrides = {}) {
  return { v: 1, state: 'state-1', nonce: 'nonce-1', verifier: 'verifier-value', exp: now + 60, ...overrides }
}

function requestUrl(code = 'auth-code', state = 'state-1') {
  return `http://127.0.0.1:3000/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
}

function named(decision, name) {
  return decision.cookies.find((cookie) => cookie.name === name)
}

function assertNoCredentialLeak(decision, secrets) {
  const rendered = `${decision.location ?? ''}\n${decision.html ?? ''}`
  for (const secret of secrets) {
    assert.equal(rendered.includes(secret), false)
  }
  const session = named(decision, SESSION_COOKIE)
  if (session?.value) {
    assert.equal(session.value.includes(secrets[0]), false)
  }
}

test('login transaction cookie is host-only, HttpOnly, and limited to the callback path', () => {
  const cookie = oidcTransactionCookie('sealed-transaction', true)
  assert.equal(cookie.name, OIDC_COOKIE)
  assert.equal(cookie.value, 'sealed-transaction')
  assert.deepEqual(cookie.options, {
    httpOnly: true,
    sameSite: 'lax',
    secure: true,
    path: '/callback',
    maxAge: 600,
  })
  assert.equal(Object.hasOwn(cookie.options, 'domain'), false)
  assert.equal(oidcTransactionCookie('sealed-transaction', false).options.secure, false)
})

test('callback locations stay on the configured sign-in origin', () => {
  assert.equal(callbackLocation(redirectUri, '/overview'), 'http://127.0.0.1:3000/overview')
  assert.equal(callbackLocation(redirectUri, '//evil.example'), null)
  assert.equal(callbackLocation(redirectUri, '/\\evil'), null)
  assert.equal(callbackLocation('http://evil.example/callback', '/overview'), 'http://evil.example/overview')
})

test('a confirmed tenant sign-in puts the session cookie on the overview redirect', () => {
  const token = accessToken({ tenant_id: tenantId })
  const started = beginCallback({
    redirectUri,
    requestUrl: requestUrl(),
    now,
    code: 'auth-code',
    state: 'state-1',
    pending: pending(),
    secure: true,
  })
  assert.equal(started.done, false)
  assert.equal(started.verifier, 'verifier-value')
  const probed = finishCallback({
    redirectUri,
    now,
    pending: pending(),
    secure: true,
    sessionKey,
    issuer,
    audience: 'oydp-api',
    clientId: 'oydp-web',
    exchange: { ok: true, accessToken: token, idToken: '' },
    jwks,
  })
  assert.equal(probed.done, false)
  assert.equal(probed.next, 'probe')
  assert.equal(probed.tenantId, tenantId)
  const finished = finishCallback({
    redirectUri,
    now,
    pending: pending(),
    secure: true,
    sessionKey,
    issuer,
    audience: 'oydp-api',
    clientId: 'oydp-web',
    exchange: { ok: true, accessToken: token, idToken: '' },
    jwks,
    propertyAccepted: true,
  })
  assert.equal(finished.done, true)
  assert.equal(finished.decision.kind, 'redirect')
  assert.equal(finished.decision.location, 'http://127.0.0.1:3000/overview')
  assertNoCredentialLeak(finished.decision, [token, 'verifier-value', 'auth-code'])
  const session = named(finished.decision, SESSION_COOKIE)
  assert.equal(session.options.httpOnly, true)
  assert.equal(session.options.sameSite, 'lax')
  assert.equal(session.options.secure, true)
  assert.equal(session.options.path, '/')
  assert.equal(session.options.maxAge, 90)
  assert.equal(Object.hasOwn(session.options, 'domain'), false)
  assert.deepEqual(decodeSession(session.value, { key: sessionKey, now }), {
    tenantId,
    accessToken: token,
    exp: now + 60 * 60 * 8,
  })
  assert.equal(named(finished.decision, OIDC_COOKIE).value, '')
  assert.equal(named(finished.decision, OIDC_COOKIE).options.path, '/callback')
  assert.equal(named(finished.decision, OIDC_COOKIE).options.maxAge, 0)
  assert.equal(named(finished.decision, PENDING_AUTH_COOKIE).value, '')
  assert.equal(named(finished.decision, PENDING_AUTH_COOKIE).options.path, '/')
})

test('a sign-in without a tenant returns one document and a pending-auth cookie', () => {
  const token = accessToken()
  const finished = finishCallback({
    redirectUri,
    now,
    pending: pending(),
    secure: false,
    sessionKey,
    issuer,
    audience: 'oydp-api',
    clientId: 'oydp-web',
    exchange: { ok: true, accessToken: token, idToken: '' },
    jwks,
  })
  assert.equal(finished.decision.kind, 'bridge')
  assert.equal(finished.decision.location, 'http://127.0.0.1:3000/connect')
  assert.equal(finished.decision.html, CONNECT_BRIDGE_HTML)
  assert.match(finished.decision.html, /href="\/connect"/)
  assert.match(finished.decision.html, />Continue</)
  assert.equal(finished.decision.html.includes('http-equiv="refresh"'), true)
  assertNoCredentialLeak(finished.decision, [token, 'verifier-value'])
  assert.equal(named(finished.decision, SESSION_COOKIE), undefined)
  const pendingCookie = named(finished.decision, PENDING_AUTH_COOKIE)
  assert.equal(pendingCookie.options.httpOnly, true)
  assert.equal(pendingCookie.options.sameSite, 'lax')
  assert.equal(pendingCookie.options.secure, false)
  assert.equal(pendingCookie.options.path, '/')
  assert.equal(pendingCookie.options.maxAge, 90)
  assert.deepEqual(openJson(pendingCookie.value, sessionKey, PENDING_AAD), {
    v: 1,
    accessToken: token,
    subject: 'alice',
    exp: now + 90,
  })
  assert.equal(named(finished.decision, OIDC_COOKIE).options.maxAge, 0)
})

test('failed callbacks clear the transaction and do not create a session', () => {
  const token = accessToken({ tenant_id: tenantId })
  const cases = [
    beginCallback({
      redirectUri,
      requestUrl: requestUrl(),
      now,
      code: '',
      state: 'state-1',
      pending: pending(),
      secure: true,
    }),
    beginCallback({
      redirectUri,
      requestUrl: requestUrl('auth-code', 'other-state'),
      now,
      code: 'auth-code',
      state: 'other-state',
      pending: pending(),
      secure: true,
    }),
    beginCallback({
      redirectUri,
      requestUrl: requestUrl(),
      now,
      code: 'auth-code',
      state: 'state-1',
      pending: pending({ exp: now - 1 }),
      secure: true,
    }),
    beginCallback({
      redirectUri,
      requestUrl: 'http://evil.example/callback?code=auth-code&state=state-1',
      now,
      code: 'auth-code',
      state: 'state-1',
      pending: pending(),
      secure: true,
    }),
    finishCallback({
      redirectUri,
      now,
      pending: pending(),
      secure: true,
      sessionKey,
      issuer,
      audience: 'oydp-api',
      clientId: 'oydp-web',
      exchange: { ok: false, accessToken: '', idToken: '' },
      jwks,
    }),
    finishCallback({
      redirectUri,
      now,
      pending: pending(),
      secure: true,
      sessionKey,
      issuer,
      audience: 'oydp-api',
      clientId: 'oydp-web',
      exchange: { ok: true, accessToken: accessToken({ nonce: 'other-nonce' }), idToken: '' },
      jwks,
    }),
    finishCallback({
      redirectUri,
      now,
      pending: pending(),
      secure: true,
      sessionKey,
      issuer,
      audience: 'oydp-api',
      clientId: 'oydp-web',
      exchange: { ok: true, accessToken: token, idToken: '' },
      jwks,
      propertyAccepted: false,
    }),
    { done: true, decision: callbackFailure(redirectUri, true, 'unavailable') },
    { done: true, decision: callbackFailure(redirectUri, true, 'redirected') },
  ]
  for (const result of cases) {
    assert.equal(result.done, true)
    assert.equal(result.decision.kind, 'redirect')
    assert.equal(result.decision.location.startsWith('http://127.0.0.1:3000/?error='), true)
    assert.equal(result.decision.location.includes('evil.example'), false)
    assert.equal(result.decision.location.includes('auth-code'), false)
    assert.equal(result.decision.location.includes(token), false)
    assert.equal(result.decision.html, null)
    assert.equal(named(result.decision, SESSION_COOKIE), undefined)
    assert.equal(named(result.decision, OIDC_COOKIE).value, '')
    assert.equal(named(result.decision, OIDC_COOKIE).options.httpOnly, true)
    assert.equal(named(result.decision, OIDC_COOKIE).options.path, '/callback')
    assert.equal(named(result.decision, PENDING_AUTH_COOKIE).value, '')
    assert.equal(named(result.decision, PENDING_AUTH_COOKIE).options.path, '/')
  }
  const propertyFailure = cases[6].decision.location
  assert.equal(decodeURIComponent(new URL(propertyFailure).searchParams.get('error')), 'Property service did not accept this sign-in')
})

test('login and callback attach auth cookies on the response they return', () => {
  const login = readFileSync(new URL('../app/login/route.ts', import.meta.url), 'utf8')
  const callback = readFileSync(new URL('../app/callback/route.ts', import.meta.url), 'utf8')
  assert.doesNotMatch(login, /jar\.set\(/)
  assert.match(login, /response\.cookies\.set\(/)
  assert.doesNotMatch(callback, /jar\.set\(/)
  assert.match(callback, /response\.cookies\.set\(/)
  assert.match(callback, /decision\.kind === 'bridge'/)
})
