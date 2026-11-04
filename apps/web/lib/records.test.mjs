import assert from 'node:assert/strict'
import test from 'node:test'
import { claimPage, formatWhen, propertyPage } from './records.mjs'

const property = {
  id: '22222222-2222-4222-8222-222222222222',
  tenant_id: '11111111-1111-4111-8111-111111111111',
  label: 'Indiranagar candidate',
  jurisdiction: 'Bengaluru Urban',
  created_by: 'alice',
  created_at: '2026-10-25T09:30:00Z',
}

test('property and claim pages keep text fields and cursors', () => {
  const page = propertyPage({ items: [property], next_cursor: 'abc_DEF' })
  assert.equal(page.items[0].label, 'Indiranagar candidate')
  assert.equal(page.nextCursor, 'abc_DEF')
  assert.equal(propertyPage({ items: [{ ...property, label: 1 }], next_cursor: null }), null)
  assert.equal(propertyPage({ items: [property], next_cursor: 'bad cursor' }), null)
  const claims = claimPage({
    items: [{
      id: '33333333-3333-4333-8333-333333333333',
      statement: 'Seller described the site.',
      created_by: 'alice',
      recorded_at: '2026-10-25T09:45:00Z',
      verification_status: 'unverified',
      kind: 'user_claim',
    }],
    next_cursor: null,
  })
  assert.equal(claims.items[0].status, 'unverified')
  assert.match(formatWhen(property.created_at), /2026/)
})
