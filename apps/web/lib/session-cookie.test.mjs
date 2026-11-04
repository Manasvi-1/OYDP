import assert from 'node:assert/strict'
import test from 'node:test'
import { asOidcTransaction, asSession, open, seal } from './session-cookie.mjs'

const secret = 'local-test-session-secret-32chars-min'

function session(exp) {
  return {
    v: 1,
    kind: 'session',
    accessToken: 'a'.repeat(40),
    tenantId: null,
    sub: 'alice',
    exp,
  }
}

test('sealed session round-trips and hides the token', () => {
  const expected = session(Date.now() + 60_000)
  const token = seal(expected, secret)
  assert.equal(token.includes('alice'), false)
  assert.deepEqual(asSession(open(token, secret)), expected)
})

test('tamper, wrong secret, expiry and short secret fail closed', () => {
  const token = seal(session(Date.now() + 60_000), secret)
  const flipped = token.slice(0, -2) + (token.endsWith('a') ? 'b' : 'a')
  assert.equal(open(flipped, secret), null)
  assert.equal(open(token, secret + '-other-characters-xxxx'), null)
  assert.equal(asSession(open(seal(session(Date.now() - 1000), secret), secret)), null)
  assert.throws(() => seal(session(Date.now() + 1000), 'too-short'))
})

test('session shape rejects a missing tenant type and blank subject', () => {
  const now = 1_000_000
  assert.equal(asSession({ ...session(now + 1), tenantId: 'not-a-uuid' }, now), null)
  assert.equal(asSession({ ...session(now + 1), sub: '   ' }, now), null)
  assert.equal(asSession({ ...session(now + 1), kind: 'oidc' }, now), null)
  const txn = asOidcTransaction({ v: 1, kind: 'oidc', state: 's'.repeat(20), verifier: 'v'.repeat(43), nonce: 'n'.repeat(16), exp: now + 1 }, now)
  assert.equal(txn.state, 's'.repeat(20))
  assert.equal(asOidcTransaction({ ...txn, exp: now - 1 }, now), null)
})
