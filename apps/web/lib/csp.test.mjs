import assert from 'node:assert/strict'
import test from 'node:test'
import { contentSecurityPolicy, useProductionCsp } from './csp.mjs'

test('production policy has no inline or eval script exception', () => {
  const policy = contentSecurityPolicy('abcdefghijk', true)
  assert.equal(policy.includes('unsafe-inline'), false)
  assert.equal(policy.includes('unsafe-eval'), false)
  assert.match(policy, /nonce-abcdefghijk/)
  assert.match(policy, /frame-ancestors 'none'/)
  assert.match(policy, /object-src 'none'/)
})

test('development policy keeps the eval exception explicit', () => {
  const policy = contentSecurityPolicy('abcdefghijk', false)
  assert.match(policy, /'unsafe-eval'/)
  assert.equal(policy.includes('unsafe-inline'), false)
})

test('production mode is true only when NODE_ENV is production', () => {
  assert.equal(useProductionCsp({ NODE_ENV: 'production' }), true)
  assert.equal(useProductionCsp({ NODE_ENV: 'development' }), false)
  assert.equal(useProductionCsp({}), false)
})

test('rejects a short nonce', () => {
  assert.throws(() => contentSecurityPolicy('short', true))
})
