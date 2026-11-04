import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import test from 'node:test'
import { decodeSession, encodeSession, openJson, sealJson } from './contract.mjs'
import { configuredApiBase, directPropertyResponse, propertyRequestUrl } from './origin.mjs'

const tenant = '11111111-1111-4111-8111-111111111111'
const key = randomBytes(32).toString('base64url')
const now = 1_700_000_000
const token = 'distinctive-access-token-value'

function session() {
  return { tenantId: tenant, accessToken: token }
}

test('seals a session without exposing the access token or an API origin', () => {
  const encoded = encodeSession(session(), { key, now })
  assert.equal(encoded.startsWith('v1.'), true)
  assert.equal(encoded.includes(token), false)
  assert.equal(encoded.includes('https://'), false)
  const opened = decodeSession(encoded, { key, now })
  assert.equal(opened.tenantId, tenant)
  assert.equal(opened.accessToken, token)
  assert.equal(Object.hasOwn(opened, 'apiBase'), false)
  assert.equal(opened.exp, now + 60 * 60 * 8)
})

test('rejects a tampered, expired, or incorrectly authenticated session', () => {
  const encoded = encodeSession(session(), { key, now })
  const flipped = encoded.slice(0, 12) + (encoded[12] === 'A' ? 'B' : 'A') + encoded.slice(13)
  assert.equal(decodeSession(flipped, { key, now }), null)
  assert.equal(decodeSession(encoded, { key: randomBytes(32).toString('base64url'), now }), null)
  assert.equal(openJson(encoded, key, 'oydp-oidc'), null)
  assert.equal(decodeSession(encoded, { key, now: now + 60 * 60 * 8 }), null)
  assert.equal(decodeSession('not-a-session', { key, now }), null)
  assert.equal(decodeSession(undefined, { key, now }), null)
})

test('rejects the previous unsigned cookie, including one that changes the API origin', () => {
  const legacy = Buffer.from(JSON.stringify({
    apiBase: 'https://evil.example',
    tenantId: tenant,
    accessToken: token,
  }), 'utf8').toString('base64url')
  assert.equal(decodeSession(legacy, { key, now }), null)
  const carried = sealJson({
    v: 1,
    tenantId: tenant,
    accessToken: token,
    exp: now + 60,
    apiBase: 'https://evil.example',
  }, key, 'oydp-session')
  assert.equal(decodeSession(carried, { key, now }), null)
})

test('takes the API origin only from server configuration', () => {
  assert.equal(configuredApiBase({}).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'http://api.example.com' }).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'https://user:pass@api.example.com' }).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'https://api.example.com/?token=1' }).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'https://api.example.com/#fragment' }).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'https://api.example.com/v1' }).ok, false)
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'https://api.example.com' }).origin, 'https://api.example.com')
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'http://127.0.0.1:8000' }).origin, 'http://127.0.0.1:8000')
  assert.equal(configuredApiBase({ PROPERTY_API_BASE: 'http://localhost:8000' }).origin, 'http://localhost:8000')
})

test('does not send a bearer token to a redirect or another origin', () => {
  const target = propertyRequestUrl('https://api.example.com', '/v1/properties?limit=1')
  assert.equal(target?.origin, 'https://api.example.com')
  assert.equal(propertyRequestUrl('https://api.example.com', 'https://evil.example/v1/properties'), null)
  assert.equal(propertyRequestUrl('https://api.example.com', '/v1/../../@evil.example'), null)
  const redirected = directPropertyResponse(302)
  assert.equal(redirected.ok, false)
  assert.equal(JSON.stringify(redirected).includes('evil.example'), false)
  assert.equal(directPropertyResponse(200).ok, true)
})
