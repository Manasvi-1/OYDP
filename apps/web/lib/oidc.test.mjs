import assert from 'node:assert/strict'
import { createSign, generateKeyPairSync } from 'node:crypto'
import test from 'node:test'
import { authorizeRequest, codeChallenge, oidcConfig, verifySignedJwt } from './oidc.mjs'

const issuer = 'http://127.0.0.1:8080/realms/oydp'
const env = {
  OIDC_ISSUER: `${issuer}/`,
  OIDC_CLIENT_ID: 'oydp-web',
  OIDC_REDIRECT_URI: 'http://127.0.0.1:3000/callback',
  OIDC_AUDIENCE: 'oydp-api',
  OIDC_JWKS_URL: 'http://127.0.0.1:8080/realms/oydp/protocol/openid-connect/certs',
  PROPERTY_API_BASE: 'http://127.0.0.1:8000',
}
const now = 1_700_000_000
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 })
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'local-1', alg: 'RS256', use: 'sig' }
const jwks = { keys: [jwk] }

function signJwt(payload, header = {}) {
  const encodedHeader = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'local-1', ...header })).toString('base64url')
  const encodedPayload = Buffer.from(JSON.stringify(payload)).toString('base64url')
  const signer = createSign('RSA-SHA256')
  signer.update(`${encodedHeader}.${encodedPayload}`)
  return `${encodedHeader}.${encodedPayload}.${signer.sign(privateKey).toString('base64url')}`
}

function idToken(overrides = {}, header = {}) {
  return signJwt({
    iss: issuer,
    aud: 'oydp-web',
    sub: 'alice',
    exp: now + 300,
    nonce: 'nonce-1',
    ...overrides,
  }, { typ: 'JWT', ...header })
}

test('builds a local sign-in configuration and hides the verifier', () => {
  const config = oidcConfig(env)
  assert.equal(config.ok, true)
  assert.equal(config.issuer, issuer)
  assert.equal(config.apiBase, 'http://127.0.0.1:8000')
  const url = authorizeRequest(config, { state: 'state-1', nonce: 'nonce-1', verifier: 'verifier-secret' })
  assert.equal(url.pathname.endsWith('/protocol/openid-connect/auth'), true)
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(url.searchParams.get('code_challenge'), codeChallenge('verifier-secret'))
  assert.equal(url.searchParams.get('verifier'), null)
  assert.equal(url.toString().includes('verifier-secret'), false)
})

test('uses loopback authorize and resource for the development issuer', () => {
  const loopback = {
    ...env,
    OIDC_ISSUER: 'http://127.0.0.1:9000',
    OIDC_JWKS_URL: 'http://127.0.0.1:9000/.well-known/jwks.json',
  }
  const config = oidcConfig(loopback)
  assert.equal(config.ok, true)
  const url = authorizeRequest(config, { state: 'state-1', nonce: 'nonce-1', verifier: 'verifier-secret' })
  assert.equal(url.pathname, '/authorize')
  assert.equal(url.searchParams.get('resource'), 'oydp-api')
})

test('rejects remote http and incomplete sign-in settings', () => {
  assert.equal(oidcConfig({}), null)
  assert.equal(oidcConfig({ OIDC_ISSUER: issuer }).ok, false)
  assert.equal(oidcConfig({ ...env, OIDC_ISSUER: 'http://identity.example.test/realms/oydp' }).ok, false)
  assert.equal(oidcConfig({ ...env, OIDC_REDIRECT_URI: 'http://user:pass@127.0.0.1:3000/callback' }).ok, false)
  assert.equal(oidcConfig({ ...env, OIDC_JWKS_URL: 'http://identity.example.test/keys' }).ok, false)
  assert.equal(oidcConfig({ ...env, PROPERTY_API_BASE: 'http://api.example.com' }).ok, false)
})

test('accepts a signed local ID token and rejects a bad signature, issuer, audience, expiry, or nonce', () => {
  const valid = verifySignedJwt(idToken(), { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' })
  assert.equal(valid.ok, true)
  assert.equal(valid.payload.sub, 'alice')
  const [h, p, s] = idToken().split('.')
  const badSignature = verifySignedJwt(`${h}.${p}.${s.slice(0, -2)}aa`, { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' })
  assert.equal(badSignature.ok, false)
  assert.equal(verifySignedJwt(idToken({ iss: 'https://evil.example' }), { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' }).ok, false)
  assert.equal(verifySignedJwt(idToken({ aud: 'other-app' }), { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' }).ok, false)
  assert.equal(verifySignedJwt(idToken({ exp: now - 1 }), { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' }).ok, false)
  assert.equal(verifySignedJwt(idToken({ nonce: 'other-nonce' }), { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' }).ok, false)
  const unsigned = `${Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ iss: issuer, aud: 'oydp-web', sub: 'alice', exp: now + 30, nonce: 'nonce-1' })).toString('base64url')}.`
  assert.equal(verifySignedJwt(unsigned, { jwks, issuer, audience: 'oydp-web', nonce: 'nonce-1', now, typ: 'JWT' }).ok, false)
})

test('accepts a signed local access token for the API audience', () => {
  const access = signJwt({
    iss: issuer,
    aud: 'oydp-api',
    sub: 'alice',
    exp: now + 300,
    tenant_id: '11111111-1111-4111-8111-111111111111',
  }, { typ: 'at+jwt' })
  const verified = verifySignedJwt(access, { jwks, issuer, audience: 'oydp-api', now, typ: 'at+jwt' })
  assert.equal(verified.ok, true)
  assert.equal(verified.payload.tenant_id, '11111111-1111-4111-8111-111111111111')
  assert.equal(verifySignedJwt(access, { jwks, issuer, audience: 'oydp-web', now, typ: 'at+jwt' }).ok, false)
})
