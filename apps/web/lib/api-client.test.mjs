import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, apiBaseAllowed, callPropertyApi, resolvePropertyPath } from './api-client.mjs'

const tenant = '11111111-1111-4111-8111-111111111111'
const propertyId = '22222222-2222-4222-8222-222222222222'
const token = 't'.repeat(40)

test('api base allows loopback http and https without credentials or paths', () => {
  assert.equal(apiBaseAllowed('http://127.0.0.1:8000'), true)
  assert.equal(apiBaseAllowed('https://api.example.test'), true)
  assert.equal(apiBaseAllowed('http://api.example.test'), false)
  assert.equal(apiBaseAllowed('https://user:secret@api.example.test'), false)
  assert.equal(apiBaseAllowed('https://api.example.test/internal'), false)
  assert.equal(apiBaseAllowed('http://127.0.0.1.example.test'), false)
})

test('property paths are an allowlist', () => {
  assert.equal(resolvePropertyPath({ kind: 'list', limit: 1, cursor: 'abc' }).path, '/v1/properties?limit=1&cursor=abc')
  assert.equal(resolvePropertyPath({ kind: 'list', cursor: '../admin' }), null)
  assert.equal(resolvePropertyPath({ kind: 'claim', id: propertyId, statement: '  noted  ' }).body.statement, 'noted')
  assert.equal(resolvePropertyPath({ kind: 'claim', id: propertyId, statement: '   ' }), null)
  assert.equal(resolvePropertyPath({ kind: 'read', id: 'not-a-uuid' }), null)
  assert.equal(resolvePropertyPath({ kind: 'create', label: 'Site', jurisdiction: 'Bengaluru Urban' }).body.label, 'Site')
})

test('calls send the bearer token only in the header and do not follow redirects', async () => {
  const seen = []
  const fetchImpl = async (url, init) => {
    seen.push({ url: String(url), init })
    return { status: 200, text: async () => JSON.stringify({ items: [], next_cursor: null }) }
  }
  const page = await callPropertyApi({
    base: 'http://127.0.0.1:8000',
    token,
    tenantId: tenant,
    request: { kind: 'list', limit: 1 },
    fetchImpl,
  })
  assert.deepEqual(page.items, [])
  assert.equal(seen[0].init.redirect, 'manual')
  assert.equal(seen[0].init.headers.Authorization, `Bearer ${token}`)
  assert.equal(seen[0].init.headers['X-Tenant-ID'], tenant)
  assert.equal(seen[0].url.includes(token), false)
  assert.equal(seen[0].init.headers.Cookie, undefined)
})

test('redirects, denials and bad tenants become stable codes', async () => {
  const redirected = async () => ({ status: 302, text: async () => '' })
  await assert.rejects(
    callPropertyApi({ base: 'http://127.0.0.1:8000', token, tenantId: tenant, request: { kind: 'list' }, fetchImpl: redirected }),
    (error) => error instanceof ApiError && error.code === 'unavailable',
  )
  const denied = async () => ({ status: 403, text: async () => JSON.stringify({ detail: 'secret deed text' }) })
  await assert.rejects(
    callPropertyApi({ base: 'http://127.0.0.1:8000', token, tenantId: tenant, request: { kind: 'create', label: 'A', jurisdiction: 'KA' }, fetchImpl: denied }),
    (error) => error instanceof ApiError && error.code === 'denied' && error.message === 'denied',
  )
  await assert.rejects(
    callPropertyApi({ base: 'http://evil.example', token, tenantId: tenant, request: { kind: 'list' }, fetchImpl: denied }),
    (error) => error.code === 'unavailable',
  )
  await assert.rejects(
    callPropertyApi({ base: 'http://127.0.0.1:8000', token, tenantId: 'guess', request: { kind: 'list' }, fetchImpl: denied }),
    (error) => error.code === 'tenant',
  )
})
