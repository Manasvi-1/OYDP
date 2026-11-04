import { parseCursor, parseUuid } from './fields.mjs'

function text(value, max) {
  return typeof value === 'string' && value.length <= max ? value : null
}

export function propertyRecord(value) {
  if (!value || typeof value !== 'object') return null
  const id = parseUuid(value.id)
  const label = text(value.label, 200)
  const jurisdiction = text(value.jurisdiction, 100)
  const createdBy = text(value.created_by, 255)
  const createdAt = text(value.created_at, 80)
  if (!id || !label || !jurisdiction || !createdBy || !createdAt) return null
  return { id, label, jurisdiction, createdBy, createdAt }
}

export function claimRecord(value) {
  if (!value || typeof value !== 'object') return null
  const id = parseUuid(value.id)
  const statement = text(value.statement, 10000)
  const createdBy = text(value.created_by, 255)
  const recordedAt = text(value.recorded_at, 80)
  const status = text(value.verification_status, 40)
  if (!id || !statement || !createdBy || !recordedAt || !status) return null
  return { id, statement, createdBy, recordedAt, status }
}

function page(value, mapItem) {
  if (!value || typeof value !== 'object' || !Array.isArray(value.items)) return null
  const items = []
  for (const item of value.items) {
    const parsed = mapItem(item)
    if (!parsed) return null
    items.push(parsed)
  }
  if (value.next_cursor == null) return { items, nextCursor: null }
  const cursor = parseCursor(value.next_cursor)
  if (!cursor) return null
  return { items, nextCursor: cursor }
}

export function propertyPage(value) {
  return page(value, propertyRecord)
}

export function claimPage(value) {
  return page(value, claimRecord)
}

export function formatWhen(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(date)
}
