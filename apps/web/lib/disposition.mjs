const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export const DISPOSITION_OUTCOMES = Object.freeze(['noted', 'kept_unresolved'])

export const DISPOSITION_SIGNAL_KINDS = Object.freeze([
  'identifier_conflict',
  'withdrawn_claim_citation',
  'withdrawn_document_citation',
  'withdrawn_review_citation',
])

/** Outcomes the web must never offer. Authorization and clearing stay on the API. */
export const FORBIDDEN_DISPOSITION_OUTCOMES = Object.freeze([
  'resolved',
  'cleared',
  'verified',
  'title',
  'merged',
  'superseded',
  'adjudicated',
  'ownership_confirmed',
])

export const DISPOSITION_NOTICE =
  'Human evidence-conflict disposition only. Not a title certificate; does not verify claims; does not clear identifier conflict status; does not merge properties.'

export const DISPOSITION_SUCCESS_NOTICE =
  'Disposition recorded. The conflict signal stays unresolved. This is not title verification or property merge.'

/**
 * @param {string} error
 * @returns {{ ok: false, error: string }}
 */
function fail(error) {
  return { ok: false, error }
}

export function isDispositionOutcome(value) {
  return DISPOSITION_OUTCOMES.includes(String(value ?? ''))
}

export function isDispositionSignalKind(value) {
  return DISPOSITION_SIGNAL_KINDS.includes(String(value ?? ''))
}

export function dispositionActionsVisible(signalKind) {
  return isDispositionSignalKind(signalKind)
}

export function visibleDispositionOutcomes() {
  return [...DISPOSITION_OUTCOMES]
}

/**
 * @param {{ signalKind?: unknown, signalId?: unknown, outcome?: unknown, reason?: unknown }} input
 * @returns {{ ok: true, body: { signal_kind: string, signal_id: string, outcome: string, reason: string } } | { ok: false, error: string }}
 */
export function parseDispositionInput(input) {
  const signalKind = String(input?.signalKind ?? '').trim()
  const signalId = String(input?.signalId ?? '').trim().toLowerCase()
  const outcome = String(input?.outcome ?? '').trim()
  const reason = String(input?.reason ?? '').trim()

  if (!isDispositionSignalKind(signalKind)) {
    return fail('Signal kind is not eligible for a disposition')
  }
  if (!UUID.test(signalId)) {
    return fail('Signal ID must be a UUID')
  }
  if (FORBIDDEN_DISPOSITION_OUTCOMES.includes(outcome)) {
    return fail('That disposition would assert resolution or title and is not allowed')
  }
  if (!isDispositionOutcome(outcome)) {
    return fail('Disposition outcome must be noted or kept_unresolved')
  }
  if (reason.length < 1 || reason.length > 500) {
    return fail('Reason must be between 1 and 500 characters')
  }
  return {
    ok: true,
    body: {
      signal_kind: signalKind,
      signal_id: signalId,
      outcome,
      reason,
    },
  }
}

export function dispositionsForSignal(dispositions, signalKind, signalId) {
  if (!Array.isArray(dispositions) || !isDispositionSignalKind(signalKind) || !UUID.test(String(signalId ?? ''))) {
    return []
  }
  const id = String(signalId).toLowerCase()
  return dispositions.filter(
    (row) => row
      && row.signal_kind === signalKind
      && String(row.signal_id ?? '').toLowerCase() === id,
  )
}

/** Dispositions never clear signals in this workspace. */
export function signalRemainsUnresolvedAfterDisposition() {
  return true
}

export function dispositionActionLabels() {
  return {
    noted: 'Note without resolving',
    kept_unresolved: 'Keep unresolved',
  }
}
