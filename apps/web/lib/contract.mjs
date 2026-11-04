const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const SESSION_COOKIE = 'oydp_session'
const MAX_TOKEN_LENGTH = 8000

function fail(error) {
  return { ok: false, error }
}

function isLocalHttp(url) {
  return url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1')
}

export function parseSessionInput(input) {
  const apiBase = String(input.apiBase ?? '').trim()
  const tenantId = String(input.tenantId ?? '').trim()
  const accessToken = String(input.accessToken ?? '').trim()
  let url
  try {
    url = new URL(apiBase)
  } catch {
    return fail('API base must be an absolute URL')
  }
  if (url.username || url.password || url.hash || url.search) {
    return fail('API base cannot include credentials, a query, or a fragment')
  }
  if (!(url.protocol === 'https:' || isLocalHttp(url))) {
    return fail('API base must be https, or http on localhost')
  }
  if (!UUID.test(tenantId)) {
    return fail('Tenant ID must be a UUID')
  }
  if (!accessToken || accessToken.includes(' ') || accessToken.length > MAX_TOKEN_LENGTH) {
    return fail('Access token must be one unspaced value that fits a browser session')
  }
  const session = {
    apiBase: url.origin,
    tenantId: tenantId.toLowerCase(),
    accessToken,
  }
  return { ok: true, session }
}

export function encodeSession(session) {
  return Buffer.from(JSON.stringify(session), 'utf8').toString('base64url')
}

export function decodeSession(value) {
  if (!value || value.length > 14000) return null
  try {
    const parsed = JSON.parse(Buffer.from(value, 'base64url').toString('utf8'))
    const check = parseSessionInput(parsed)
    return check.ok ? check.session : null
  } catch {
    return null
  }
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

export { SESSION_COOKIE, UUID }
