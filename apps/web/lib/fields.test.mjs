import assert from 'node:assert/strict'
import test from 'node:test'
import { errorText, pageSize, parseCursor, parsePropertyInput, parseStatement, parseUuid } from './fields.mjs'

test('errors stay on the known list', () => {
  assert.match(errorText('denied'), /MFA/)
  assert.equal(errorText('javascript:alert(1)'), '')
  assert.equal(errorText(undefined), '')
})

test('pagination and record fields fail closed', () => {
  assert.equal(parseUuid('11111111-1111-4111-8111-111111111111'), '11111111-1111-4111-8111-111111111111')
  assert.equal(parseUuid('11111111-1111-4111-8111-111111111111\n'), null)
  assert.equal(parseCursor(undefined), '')
  assert.equal(parseCursor('abc_DEF-012'), 'abc_DEF-012')
  assert.equal(parseCursor('bad.cursor'), null)
  assert.equal(parseCursor('a'.repeat(513)), null)
  assert.equal(pageSize(undefined), 25)
  assert.equal(pageSize('1'), 1)
  assert.equal(pageSize('0'), null)
  assert.equal(pageSize('101'), null)
  assert.equal(pageSize('25abc'), null)
  assert.deepEqual(parsePropertyInput('  Site  ', ' Bengaluru Urban '), { label: 'Site', jurisdiction: 'Bengaluru Urban' })
  assert.equal(parsePropertyInput(' ', 'KA'), null)
  assert.equal(parseStatement('  A seller said this.  '), 'A seller said this.')
  assert.equal(parseStatement('   '), null)
})
