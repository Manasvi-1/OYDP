import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DISPOSITION_NOTICE,
  DISPOSITION_OUTCOMES,
  DISPOSITION_SIGNAL_KINDS,
  DISPOSITION_SUCCESS_NOTICE,
  FORBIDDEN_DISPOSITION_OUTCOMES,
  dispositionActionLabels,
  dispositionActionsVisible,
  dispositionsForSignal,
  parseDispositionInput,
  signalRemainsUnresolvedAfterDisposition,
  visibleDispositionOutcomes,
} from './disposition.mjs'

const signalId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
const otherId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'

test('UI contract exposes only noted and kept_unresolved outcomes', () => {
  assert.deepEqual(visibleDispositionOutcomes(), ['noted', 'kept_unresolved'])
  assert.deepEqual([...DISPOSITION_OUTCOMES], ['noted', 'kept_unresolved'])
  const labels = dispositionActionLabels()
  assert.equal(Object.keys(labels).sort().join(','), 'kept_unresolved,noted')
  for (const forbidden of FORBIDDEN_DISPOSITION_OUTCOMES) {
    assert.equal(visibleDispositionOutcomes().includes(forbidden), false)
  }
  assert.match(DISPOSITION_NOTICE, /does not verify claims/)
  assert.match(DISPOSITION_SUCCESS_NOTICE, /stays unresolved/)
  assert.equal(signalRemainsUnresolvedAfterDisposition(), true)
})

test('action visibility is limited to dispositionable signal kinds', () => {
  for (const kind of DISPOSITION_SIGNAL_KINDS) {
    assert.equal(dispositionActionsVisible(kind), true)
  }
  assert.equal(dispositionActionsVisible('multiple_open_unverified_claims'), false)
  assert.equal(dispositionActionsVisible('title_verification'), false)
  assert.equal(dispositionActionsVisible('property_merge'), false)
  assert.equal(dispositionActionsVisible(''), false)
})

test('parseDispositionInput builds the API body and rejects invalid paths', () => {
  const ok = parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId,
    outcome: 'noted',
    reason: '  Reviewer saw the duplicate identifier row.  ',
  })
  assert.equal(ok.ok, true)
  assert.deepEqual(ok.body, {
    signal_kind: 'identifier_conflict',
    signal_id: signalId,
    outcome: 'noted',
    reason: 'Reviewer saw the duplicate identifier row.',
  })

  assert.equal(parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId,
    outcome: 'kept_unresolved',
    reason: 'Leave open',
  }).ok, true)

  assert.match(parseDispositionInput({
    signalKind: 'property_merge',
    signalId,
    outcome: 'noted',
    reason: 'Nope',
  }).error, /not eligible/)

  assert.match(parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId: 'not-a-uuid',
    outcome: 'noted',
    reason: 'Nope',
  }).error, /UUID/)

  assert.match(parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId,
    outcome: 'verified',
    reason: 'Would be title-like',
  }).error, /resolution or title/)

  assert.match(parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId,
    outcome: 'cleared',
    reason: 'Would clear',
  }).error, /resolution or title/)

  assert.match(parseDispositionInput({
    signalKind: 'identifier_conflict',
    signalId,
    outcome: 'recorded',
    reason: 'Wrong enum',
  }).error, /noted or kept_unresolved/)

  assert.match(parseDispositionInput({
    signalKind: 'withdrawn_claim_citation',
    signalId,
    outcome: 'noted',
    reason: '',
  }).error, /Reason/)

  assert.match(parseDispositionInput({
    signalKind: 'withdrawn_document_citation',
    signalId,
    outcome: 'noted',
    reason: 'x'.repeat(501),
  }).error, /Reason/)
})

test('dispositions attach beside matching conflict signals only', () => {
  const rows = [
    { id: '1', signal_kind: 'identifier_conflict', signal_id: signalId, outcome: 'noted', recorded_at: '2026-11-26T10:00:00Z' },
    { id: '2', signal_kind: 'withdrawn_claim_citation', signal_id: signalId, outcome: 'kept_unresolved', recorded_at: '2026-11-26T11:00:00Z' },
    { id: '3', signal_kind: 'identifier_conflict', signal_id: otherId, outcome: 'noted', recorded_at: '2026-11-26T12:00:00Z' },
  ]
  const matched = dispositionsForSignal(rows, 'identifier_conflict', signalId)
  assert.equal(matched.length, 1)
  assert.equal(matched[0].id, '1')
  assert.equal(dispositionsForSignal(rows, 'withdrawn_claim_citation', signalId).length, 1)
  assert.equal(dispositionsForSignal(rows, 'identifier_conflict', otherId).length, 1)
  assert.equal(dispositionsForSignal(rows, 'withdrawn_review_citation', signalId).length, 0)
  assert.equal(dispositionsForSignal(null, 'identifier_conflict', signalId).length, 0)
  assert.equal(dispositionsForSignal(rows, 'title_verification', signalId).length, 0)
})
