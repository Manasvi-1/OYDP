import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DEDUP_NOTICE,
  DEDUP_REVIEW_NOTICE,
  DEDUP_REVIEW_OUTCOMES,
  DEDUP_SUCCESS_NOTICE,
  FORBIDDEN_DEDUP_OUTCOMES,
  dedupReviewActionLabels,
  parseDedupReviewInput,
  propertiesRemainUnmergedAfterReview,
  visibleDedupReviewOutcomes,
} from './dedup.mjs'

const candidateId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

test('UI contract exposes only non-merge dedup review outcomes', () => {
  assert.deepEqual(visibleDedupReviewOutcomes(), [
    'keep_separate',
    'flag_possible_duplicate',
    'needs_more_evidence',
  ])
  assert.deepEqual([...DEDUP_REVIEW_OUTCOMES], visibleDedupReviewOutcomes())
  const labels = dedupReviewActionLabels()
  assert.equal(
    Object.keys(labels).sort().join(','),
    'flag_possible_duplicate,keep_separate,needs_more_evidence',
  )
  for (const forbidden of FORBIDDEN_DEDUP_OUTCOMES) {
    assert.equal(visibleDedupReviewOutcomes().includes(forbidden), false)
  }
  assert.match(DEDUP_NOTICE, /never merge properties/i)
  assert.match(DEDUP_REVIEW_NOTICE, /does not merge properties/i)
  assert.match(DEDUP_SUCCESS_NOTICE, /were not merged/i)
  assert.equal(propertiesRemainUnmergedAfterReview(), true)
})

test('parseDedupReviewInput builds the API body and rejects merge-like paths', () => {
  const ok = parseDedupReviewInput({
    candidateId,
    outcome: 'keep_separate',
    reason: '  These look similar but remain separate records.  ',
  })
  assert.equal(ok.ok, true)
  assert.equal(ok.candidateId, candidateId)
  assert.deepEqual(ok.body, {
    outcome: 'keep_separate',
    reason: 'These look similar but remain separate records.',
  })

  assert.equal(parseDedupReviewInput({
    candidateId,
    outcome: 'merge',
    reason: 'Must not merge',
  }).ok, false)
  assert.equal(parseDedupReviewInput({
    candidateId,
    outcome: 'verified',
    reason: 'Must not verify',
  }).ok, false)
  assert.equal(parseDedupReviewInput({
    candidateId: 'not-a-uuid',
    outcome: 'keep_separate',
    reason: 'Bad id',
  }).ok, false)
  assert.equal(parseDedupReviewInput({
    candidateId,
    outcome: 'keep_separate',
    reason: '',
  }).ok, false)
})
