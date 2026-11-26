export const DEDUP_REVIEW_OUTCOMES: readonly [
  'keep_separate',
  'flag_possible_duplicate',
  'needs_more_evidence',
]
export const FORBIDDEN_DEDUP_OUTCOMES: readonly string[]
export const DEDUP_NOTICE: string
export const DEDUP_REVIEW_NOTICE: string
export const DEDUP_SUCCESS_NOTICE: string

export function isDedupReviewOutcome(value: unknown): boolean
export function visibleDedupReviewOutcomes(): string[]
export function dedupReviewActionLabels(): {
  keep_separate: string
  flag_possible_duplicate: string
  needs_more_evidence: string
}
export function propertiesRemainUnmergedAfterReview(): true
export function parseDedupReviewInput(input: {
  candidateId?: unknown
  outcome?: unknown
  reason?: unknown
}):
  | { ok: true; candidateId: string; body: { outcome: string; reason: string } }
  | { ok: false; error: string }
