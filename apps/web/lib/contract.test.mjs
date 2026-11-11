import assert from 'node:assert/strict'
import test from 'node:test'
import { auditQuery, claimsQuery, correctionsQuery, documentsQuery, evidenceConflictsQuery, evidenceGraphQuery, identifiersQuery, messageFromApi, parseSessionInput, propertiesQuery, reviewsQuery, sourcesQuery } from './contract.mjs'

const tenant = '11111111-1111-4111-8111-111111111111'

test('accepts a tenant and token and rejects a caller-supplied API origin', () => {
  const result = parseSessionInput({ tenantId: tenant.toUpperCase(), accessToken: 'header.payload.signature' })
  assert.equal(result.ok, true)
  assert.equal(result.session.tenantId, tenant)
  assert.equal(Object.hasOwn(result.session, 'apiBase'), false)
  const injected = parseSessionInput({
    apiBase: 'https://evil.example',
    tenantId: tenant,
    accessToken: 'header.payload.signature',
  })
  assert.equal(injected.ok, false)
})

test('rejects a malformed tenant or token', () => {
  assert.equal(parseSessionInput({ tenantId: 'not-a-uuid', accessToken: 'a.b.c' }).ok, false)
  assert.equal(parseSessionInput({ tenantId: tenant, accessToken: 'two tokens' }).ok, false)
  assert.equal(parseSessionInput({ tenantId: tenant, accessToken: '' }).ok, false)
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
  assert.equal(correctionsQuery(tenant, undefined), `/v1/properties/${tenant}/corrections?limit=25`)
  assert.equal(identifiersQuery(tenant, undefined), `/v1/properties/${tenant}/identifiers?limit=25`)
  assert.equal(reviewsQuery(tenant, 'next'), `/v1/properties/${tenant}/reviews?limit=25&cursor=next`)
  assert.equal(documentsQuery(tenant, undefined), `/v1/properties/${tenant}/documents?limit=25`)
  assert.equal(auditQuery(tenant, undefined), `/v1/properties/${tenant}/audit?limit=25`)
  assert.equal(sourcesQuery(undefined), '/v1/sources?limit=25')
  assert.equal(evidenceGraphQuery(tenant), `/v1/properties/${tenant}/evidence-graph`)
  assert.equal(evidenceConflictsQuery(tenant), `/v1/properties/${tenant}/evidence-conflicts`)
  assert.equal(messageFromApi(403, { detail: 'Export consent required' }), 'Export consent required')
  assert.equal(messageFromApi(422, { detail: 'Source is withdrawn' }), 'Source is withdrawn')
  assert.equal(messageFromApi(422, { detail: 'Identifier resolution required' }), 'Identifier resolution required')
})
