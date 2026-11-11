import assert from 'node:assert/strict'
import test from 'node:test'
import { buildCspEnvelope, freshCspNonce } from '../lib/csp-apply.mjs'

test('fresh CSP nonces are 32-byte base64 values', () => {
  const nonce = freshCspNonce()
  assert.match(nonce, /^[A-Za-z0-9+/]+=*$/)
  assert.equal(Buffer.from(nonce, 'base64').length, 32)
})

test('CSP envelope replaces any caller-supplied nonce and forbids unsafe-inline scripts in production', () => {
  const forged = 'forged-nonce-aaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  const envelope = buildCspEnvelope({ NODE_ENV: 'production' })
  assert.equal(envelope.nonce === forged, false)
  assert.equal(envelope.policy.includes('unsafe-inline'), false)
  assert.equal(envelope.policy.includes(forged), false)
  assert.match(envelope.policy, /'nonce-[A-Za-z0-9+/=_-]{8,}'/)
  assert.equal(envelope.requestHeaders['x-nonce'], envelope.nonce)
  assert.equal(envelope.requestHeaders['Content-Security-Policy'], envelope.policy)
})
