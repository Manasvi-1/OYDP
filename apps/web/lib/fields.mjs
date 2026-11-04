const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const CURSOR = /^[A-Za-z0-9_-]{1,512}$/

export const ERROR_TEXT = {
  signin: 'Sign-in did not complete, or the access token expired. Start again.',
  denied: 'This membership or MFA claim does not allow that action.',
  invalid: 'Those fields were not accepted.',
  missing: 'That property is not available in this workspace.',
  unavailable: 'The property service is unavailable.',
  tenant: 'That tenant is not available for this sign-in.',
}

export function errorText(code) {
  return Object.prototype.hasOwnProperty.call(ERROR_TEXT, code) ? ERROR_TEXT[code] : ''
}

export function parseUuid(value) {
  return typeof value === 'string' && UUID.test(value) ? value.toLowerCase() : null
}

export function parseCursor(value) {
  if (value == null || value === '') return ''
  return typeof value === 'string' && CURSOR.test(value) ? value : null
}

export function pageSize(raw) {
  if (raw == null || raw === '') return 25
  if (!/^[0-9]+$/.test(String(raw))) return null
  const size = Number(raw)
  return size >= 1 && size <= 100 ? size : null
}

function bounded(value, max) {
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (text.length < 1 || text.length > max) return null
  return text
}

export function parsePropertyInput(label, jurisdiction) {
  const cleanLabel = bounded(label, 200)
  const cleanJurisdiction = bounded(jurisdiction, 100)
  if (!cleanLabel || !cleanJurisdiction) return null
  return { label: cleanLabel, jurisdiction: cleanJurisdiction }
}

export function parseStatement(value) {
  return bounded(value, 10000)
}
