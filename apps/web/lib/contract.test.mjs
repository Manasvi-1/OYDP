import assert from 'node:assert/strict'
import test from 'node:test'
import {
  claimsQuery,
  decodeSession,
  encodeSession,
  messageFromApi,
  parseSessionInput,
  propertiesQuery,
} from './contract.mjs'

const tenant = '11111111-1111-4111-8111-111111111111'

test('accepts a local API base and normalizes the tenant id', () => {
  const result = parseSessionInput({
    apiBase: 'http://localhost:8000/ignored',
    tenantId: tenant.toUpperCase(),
    accessToken: 'header.payload.signature',
  })
  assert.equal(result.ok, true)
  assert.equal(result.session.apiBase, 'http://localhost:8000')
  assert.equal(result.session.tenantId, tenant)
})

test('rejects insecure remote bases, credentials, and malformed sessions', () => {
  assert.equal(parseSessionInput({ apiBase: 'http://example.com', tenantId: tenant, accessToken: 'a.b.c' }).ok, false)
  assert.equal(parseSessionInput({ apiBase: 'https://user:pass@example.com', tenantId: tenant, accessToken: 'a.b.c' }).ok, false)
  assert.equal(parseSessionInput({ apiBase: 'https://example.com/?q=1', tenantId: tenant, accessToken: 'a.b.c' }).ok, false)
  assert.equal(parseSessionInput({ apiBase: 'https://example.com', tenantId: 'not-a-uuid', accessToken: 'a.b.c' }).ok, false)
  assert.equal(parseSessionInput({ apiBase: 'https://example.com', tenantId: tenant, accessToken: 'two tokens' }).ok, false)
})

test('round-trips a session and rejects tampered cookies', () => {
  const parsed = parseSessionInput({ apiBase: 'https://api.example.com', tenantId: tenant, accessToken: 'a.b.c' })
  const encoded = encodeSession(parsed.session)
  assert.deepEqual(decodeSession(encoded), parsed.session)
  assert.equal(decodeSession('not-json'), null)
  assert.equal(decodeSession(encodeSession({ apiBase: 'http://example.com', tenantId: tenant, accessToken: 'a.b.c' })), null)
})

test('uses API detail text and falls back without echoing unexpected bodies', () => {
  assert.equal(messageFromApi(403, { detail: 'MFA access token required' }), 'MFA access token required')
  assert.equal(messageFromApi(500, { detail: { secret: 'nope' } }), 'The property service could not complete this request')
  assert.equal(messageFromApi(422, {}), 'Invalid request')
})

test('builds bounded property and claim queries', () => {
  assert.equal(propertiesQuery(undefined), '/v1/properties?limit=25')
  assert.equal(propertiesQuery('cursor+value'), '/v1/properties?limit=25&cursor=cursor%2Bvalue')
  assert.equal(claimsQuery(tenant, undefined), `/v1/properties/${tenant}/claims?limit=25`)
})
