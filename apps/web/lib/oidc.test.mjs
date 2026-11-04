import assert from 'node:assert/strict'
import test from 'node:test'
import { authorizeRequest, codeChallenge, oidcConfig, readUnverifiedStringClaim } from './oidc.mjs'

const env = {
  OIDC_ISSUER: 'http://127.0.0.1:8080/realms/oydp/',
  OIDC_CLIENT_ID: 'oydp-web',
  OIDC_REDIRECT_URI: 'http://127.0.0.1:3000/callback',
  PROPERTY_API_BASE: 'http://127.0.0.1:8000',
}

test('builds a local sign-in configuration and hides the verifier', () => {
  const config = oidcConfig(env)
  assert.equal(config.ok, true)
  assert.equal(config.issuer, 'http://127.0.0.1:8080/realms/oydp')
  const url = authorizeRequest(config, { state: 'state-1', nonce: 'nonce-1', verifier: 'verifier-secret' })
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(url.searchParams.get('code_challenge'), codeChallenge('verifier-secret'))
  assert.equal(url.searchParams.get('verifier'), null)
  assert.equal(url.toString().includes('verifier-secret'), false)
})

test('rejects remote http and incomplete sign-in settings', () => {
  assert.equal(oidcConfig({}), null)
  assert.equal(oidcConfig({ OIDC_ISSUER: 'http://127.0.0.1:8080/realms/oydp' }).ok, false)
  assert.equal(oidcConfig({ ...env, OIDC_ISSUER: 'http://identity.example.test/realms/oydp' }).ok, false)
  assert.equal(oidcConfig({ ...env, OIDC_REDIRECT_URI: 'http://user:pass@127.0.0.1:3000/callback' }).ok, false)
})

test('reads only string claims from an unverified token payload', () => {
  const payload = Buffer.from(JSON.stringify({ tenant_id: 'abc', nonce: 4 })).toString('base64url')
  const token = `header.${payload}.signature`
  assert.equal(readUnverifiedStringClaim(token, 'tenant_id'), 'abc')
  assert.equal(readUnverifiedStringClaim(token, 'nonce'), '')
  assert.equal(readUnverifiedStringClaim('not-a-token', 'tenant_id'), '')
})
