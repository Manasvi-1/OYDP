import assert from 'node:assert/strict'
import { createSign, generateKeyPairSync } from 'node:crypto'
import test from 'node:test'
import {
  accessTokenFromResponse,
  authorizeUrl,
  endpointAllowed,
  endpointsFromDiscovery,
  idTokenNonceMatches,
  oidcConfig,
  pkceChallenge,
  sameState,
  verifyAccessToken,
} from './oidc.mjs'

const env = {
  OIDC_ISSUER: 'http://127.0.0.1:9000',
  OIDC_CLIENT_ID: 'oydp-web',
  OIDC_REDIRECT_URI: 'http://127.0.0.1:3000/auth/callback',
  OIDC_AUDIENCE: 'oydp-api',
  OYDP_OIDC_DEV_HTTP: '1',
}

function sign(privateKey, header, claims) {
  const h64 = Buffer.from(JSON.stringify(header)).toString('base64url')
  const p64 = Buffer.from(JSON.stringify(claims)).toString('base64url')
  const signer = createSign('RSA-SHA256')
  signer.update(`${h64}.${p64}`)
  signer.end()
  return `${h64}.${p64}.${signer.sign(privateKey).toString('base64url')}`
}

test('loopback http is opt-in and public http stays closed', () => {
  assert.equal(endpointAllowed('https://identity.example.test/realms/oydp', ''), true)
  assert.equal(endpointAllowed('http://127.0.0.1:9000', ''), false)
  assert.equal(endpointAllowed('http://127.0.0.1:9000', '1'), true)
  assert.equal(endpointAllowed('http://identity.example.test', '1'), false)
  assert.equal(endpointAllowed('http://127.0.0.1.example.test', '1'), false)
  assert.equal(endpointAllowed('https://user:pass@identity.example.test', '1'), false)
  assert.equal(oidcConfig({ ...env, OYDP_OIDC_DEV_HTTP: '' }), null)
  assert.equal(oidcConfig({ ...env, OIDC_ISSUER: 'https://evil.example' }).issuer, 'https://evil.example')
})

test('discovery endpoints must stay on the issuer origin', () => {
  const issuer = 'http://127.0.0.1:9000'
  const good = endpointsFromDiscovery({
    issuer,
    authorization_endpoint: issuer + '/authorize',
    token_endpoint: issuer + '/token',
    jwks_uri: issuer + '/.well-known/jwks.json',
  }, issuer)
  assert.equal(good.token, issuer + '/token')
  assert.equal(endpointsFromDiscovery({ ...good, issuer: 'https://evil.example', authorization_endpoint: 'https://evil.example/a', token_endpoint: 'https://evil.example/t', jwks_uri: 'https://evil.example/j' }, issuer), null)
  assert.equal(endpointsFromDiscovery({
    issuer,
    authorization_endpoint: 'http://evil.example/authorize',
    token_endpoint: issuer + '/token',
    jwks_uri: issuer + '/jwks',
  }, issuer), null)
})

test('authorize URL carries PKCE and never the verifier', () => {
  const pkce = pkceChallenge()
  const config = oidcConfig(env)
  const url = new URL(authorizeUrl('http://127.0.0.1:9000/authorize', { ...config, ...pkce }))
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(url.searchParams.get('code_challenge'), pkce.challenge)
  assert.equal(url.searchParams.get('code_verifier'), null)
  assert.equal(url.searchParams.get('response_type'), 'code')
  assert.equal(url.searchParams.get('resource'), 'oydp-api')
  assert.equal(sameState(pkce.state, pkce.state), true)
  assert.equal(sameState(pkce.state, pkce.nonce), false)
})

test('access token verification accepts only the API profile', () => {
  const { publicKey, privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 })
  const jwk = publicKey.export({ format: 'jwk' })
  jwk.kid = 'dev-1'
  jwk.alg = 'RS256'
  const now = 1_700_000_000
  const header = { alg: 'RS256', typ: 'at+jwt', kid: 'dev-1' }
  const claims = { iss: 'http://127.0.0.1:9000', aud: 'oydp-api', sub: 'alice', iat: now, exp: now + 600, amr: ['pwd', 'mfa'] }
  const token = sign(privateKey, header, claims)
  assert.equal(verifyAccessToken(token, { keys: [jwk] }, { issuer: claims.iss, audience: 'oydp-api', now }).sub, 'alice')
  assert.throws(() => verifyAccessToken(sign(privateKey, { ...header, typ: 'JWT' }, claims), { keys: [jwk] }, { issuer: claims.iss, audience: 'oydp-api', now }))
  assert.throws(() => verifyAccessToken(sign(privateKey, { alg: 'none', typ: 'at+jwt', kid: 'dev-1' }, claims) + '.', { keys: [jwk] }, { issuer: claims.iss, audience: 'oydp-api', now }))
  assert.throws(() => verifyAccessToken(token, { keys: [jwk] }, { issuer: claims.iss, audience: 'other', now }))
  assert.throws(() => verifyAccessToken(token, { keys: [jwk] }, { issuer: claims.iss, audience: 'oydp-api', now: now + 1000 }))
  const other = generateKeyPairSync('rsa', { modulusLength: 2048 }).privateKey
  assert.throws(() => verifyAccessToken(sign(other, header, claims), { keys: [jwk] }, { issuer: claims.iss, audience: 'oydp-api', now }))
  assert.equal(accessTokenFromResponse({ access_token: token, token_type: 'Bearer' }), token)
  assert.equal(accessTokenFromResponse({ access_token: token, token_type: 'id' }), null)
  assert.equal(idTokenNonceMatches(sign(privateKey, header, { nonce: 'n'.repeat(16) }), 'n'.repeat(16)), true)
  assert.equal(idTokenNonceMatches(sign(privateKey, header, { nonce: 'other-nonce-value' }), 'n'.repeat(16)), false)
})
