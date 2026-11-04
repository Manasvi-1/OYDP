import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const SESSION_COOKIE = 'oydp_session'
const MAX_TOKEN_LENGTH = 8000
const SESSION_TTL_SECONDS = 60 * 60 * 8
const SESSION_PREFIX = 'v1.'
const SESSION_AAD = 'oydp-session'

function fail(error) {
  return { ok: false, error }
}

export function sessionKeyBytes(key) {
  const raw = String(key ?? '').trim()
  if (!raw || raw.length > 128) return null
  const bytes = Buffer.from(raw, 'base64url')
  if (bytes.length !== 32 || bytes.toString('base64url') !== raw) return null
  return bytes
}

export function sealJson(payload, key, aad) {
  const keyBytes = sessionKeyBytes(key)
  if (!keyBytes) throw new Error('Session key is not configured')
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', keyBytes, iv)
  cipher.setAAD(Buffer.from(aad))
  const ciphertext = Buffer.concat([cipher.update(Buffer.from(JSON.stringify(payload), 'utf8')), cipher.final()])
  const tag = cipher.getAuthTag()
  return SESSION_PREFIX + Buffer.concat([iv, ciphertext, tag]).toString('base64url')
}

export function openJson(value, key, aad) {
  const keyBytes = sessionKeyBytes(key)
  if (!keyBytes || typeof value !== 'string' || !value.startsWith(SESSION_PREFIX) || value.length > 14000) return null
  try {
    const packed = Buffer.from(value.slice(SESSION_PREFIX.length), 'base64url')
    if (packed.length < 12 + 16 + 2) return null
    const iv = packed.subarray(0, 12)
    const tag = packed.subarray(packed.length - 16)
    const ciphertext = packed.subarray(12, packed.length - 16)
    const decipher = createDecipheriv('aes-256-gcm', keyBytes, iv)
    decipher.setAAD(Buffer.from(aad))
    decipher.setAuthTag(tag)
    const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()])
    const payload = JSON.parse(plaintext.toString('utf8'))
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null
    return payload
  } catch {
    return null
  }
}

export function parseSessionInput(input) {
  if (input && Object.prototype.hasOwnProperty.call(input, 'apiBase') && String(input.apiBase ?? '').trim()) {
    return fail('API origin is configured on the server')
  }
  const tenantId = String(input?.tenantId ?? '').trim()
  const accessToken = String(input?.accessToken ?? '').trim()
  if (!UUID.test(tenantId)) return fail('Tenant ID must be a UUID')
  if (!accessToken || accessToken.includes(' ') || accessToken.length > MAX_TOKEN_LENGTH) {
    return fail('Access token must be one unspaced value that fits a browser session')
  }
  return { ok: true, session: { tenantId: tenantId.toLowerCase(), accessToken } }
}

export function encodeSession(session, options) {
  if (session && Object.prototype.hasOwnProperty.call(session, 'apiBase')) {
    throw new Error('API origin is not part of the session')
  }
  const parsed = parseSessionInput(session)
  if (!parsed.ok) throw new Error(parsed.error)
  const now = Number(options?.now)
  if (!Number.isFinite(now)) throw new Error('Session time is required')
  return sealJson({
    v: 1,
    tenantId: parsed.session.tenantId,
    accessToken: parsed.session.accessToken,
    exp: now + SESSION_TTL_SECONDS,
  }, options.key, SESSION_AAD)
}

export function decodeSession(value, options) {
  const now = Number(options?.now)
  if (!Number.isFinite(now)) return null
  const payload = openJson(value, options?.key, SESSION_AAD)
  if (!payload || payload.v !== 1 || Object.prototype.hasOwnProperty.call(payload, 'apiBase')) return null
  if (typeof payload.exp !== 'number' || payload.exp <= now) return null
  const parsed = parseSessionInput({ tenantId: payload.tenantId, accessToken: payload.accessToken })
  if (!parsed.ok) return null
  return { ...parsed.session, exp: payload.exp }
}

export function messageFromApi(status, payload) {
  const detail = payload && typeof payload.detail === 'string' ? payload.detail.trim() : ''
  if (detail && detail.length <= 300) return detail
  if (status === 401) return 'Bearer access token required'
  if (status === 403) return 'This session cannot perform that action'
  if (status === 404) return 'Property not found'
  if (status === 422) return 'Invalid request'
  if (status === 503) return 'Property service unavailable'
  return 'The property service could not complete this request'
}

export function propertiesQuery(cursor) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  return `/v1/properties?${params.toString()}`
}

export function correctionsQuery(propertyId, cursor) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  return `/v1/properties/${propertyId}/corrections?${params.toString()}`
}

export function claimsQuery(propertyId, cursor) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  return `/v1/properties/${propertyId}/claims?${params.toString()}`
}

function propertyQuery(propertyId, suffix, cursor) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  return `/v1/properties/${propertyId}/${suffix}?${params.toString()}`
}

export function identifiersQuery(propertyId, cursor) {
  return propertyQuery(propertyId, 'identifiers', cursor)
}

export function reviewsQuery(propertyId, cursor) {
  return propertyQuery(propertyId, 'reviews', cursor)
}

export function documentsQuery(propertyId, cursor) {
  return propertyQuery(propertyId, 'documents', cursor)
}

export function auditQuery(propertyId, cursor) {
  return propertyQuery(propertyId, 'audit', cursor)
}

export function sourcesQuery(cursor) {
  const params = new URLSearchParams({ limit: '25' })
  if (cursor) params.set('cursor', cursor)
  return `/v1/sources?${params.toString()}`
}

export { SESSION_COOKIE, UUID }
