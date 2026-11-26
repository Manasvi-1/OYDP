const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export const DEDUP_REVIEW_OUTCOMES = Object.freeze([
  'keep_separate',
  'flag_possible_duplicate',
  'needs_more_evidence',
])

/** Outcomes the web must never offer. Merge and title stay impossible here. */
export const FORBIDDEN_DEDUP_OUTCOMES = Object.freeze([
  'merge',
  'merged',
  'same_title',
  'verified',
  'title',
  'accepted',
  'cleared',
  'ownership_confirmed',
])

export const DEDUP_NOTICE =
  'Property deduplication candidate only. Same-tenant evidence similarity is not title proof; candidates never merge properties, verify claims, clear conflicts, or assert ownership.'

export const DEDUP_REVIEW_NOTICE =
  'Human deduplication review only. Not a title certificate; does not merge properties; does not verify claims; does not clear identifier conflict status.'

export const DEDUP_SUCCESS_NOTICE =
  'Review recorded. Properties were not merged. This is not title verification.'

/**
 * @param {string} error
 * @returns {{ ok: false, error: string }}
 */
function fail(error) {
  return { ok: false, error }
}

export function isDedupReviewOutcome(value) {
  return DEDUP_REVIEW_OUTCOMES.includes(String(value ?? ''))
}

export function visibleDedupReviewOutcomes() {
  return [...DEDUP_REVIEW_OUTCOMES]
}

export function dedupReviewActionLabels() {
  return {
    keep_separate: 'Keep separate',
    flag_possible_duplicate: 'Flag possible duplicate',
    needs_more_evidence: 'Needs more evidence',
  }
}

/** Candidates never merge properties in this workspace. */
export function propertiesRemainUnmergedAfterReview() {
  return true
}

/**
 * @param {{ candidateId?: unknown, outcome?: unknown, reason?: unknown }} input
 * @returns {{ ok: true, body: { outcome: string, reason: string }, candidateId: string } | { ok: false, error: string }}
 */
export function parseDedupReviewInput(input) {
  const candidateId = String(input?.candidateId ?? '').trim().toLowerCase()
  const outcome = String(input?.outcome ?? '').trim()
  const reason = String(input?.reason ?? '').trim()

  if (!UUID.test(candidateId)) {
    return fail('Candidate ID must be a UUID')
  }
  if (FORBIDDEN_DEDUP_OUTCOMES.includes(outcome)) {
    return fail('That review would merge properties or assert title and is not allowed')
  }
  if (!isDedupReviewOutcome(outcome)) {
    return fail('Review outcome must be keep_separate, flag_possible_duplicate, or needs_more_evidence')
  }
  if (reason.length < 1 || reason.length > 500) {
    return fail('Reason must be between 1 and 500 characters')
  }
  return {
    ok: true,
    candidateId,
    body: { outcome, reason },
  }
}
