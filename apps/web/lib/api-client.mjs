import { parseCursor, parsePropertyInput, parseStatement, parseUuid } from './fields.mjs'

export class ApiError extends Error {
  constructor(code) {
    super(code)
    this.name = 'ApiError'
    this.code = code
  }
}

export function apiBaseAllowed(value) {
  let url
  try {
    url = new URL(value)
  } catch {
    return false
  }
  if (url.username || url.password || url.hash || url.search) return false
  if (url.pathname !== '/' && url.pathname !== '') return false
  if (url.protocol === 'https:') return Boolean(url.hostname)
  const host = url.hostname.toLowerCase().replace(/\.$/, '')
  return url.protocol === 'http:' && (host === '127.0.0.1' || host === 'localhost')
}

export function codeForStatus(status) {
  if (status === 401) return 'signin'
  if (status === 403) return 'denied'
  if (status === 404) return 'missing'
  if (status === 422) return 'invalid'
  return 'unavailable'
}

function cursorQuery(cursor) {
  const parsed = parseCursor(cursor)
  if (parsed == null) return null
  return parsed ? `&cursor=${parsed}` : ''
}

export function resolvePropertyPath(request) {
  const limit = request.limit ?? 25
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) return null
  const cursor = cursorQuery(request.cursor)
  if (cursor == null) return null
  if (request.kind === 'list') return { method: 'GET', path: `/v1/properties?limit=${limit}${cursor}` }
  if (request.kind === 'create') {
    const fields = parsePropertyInput(request.label, request.jurisdiction)
    if (!fields) return null
    return { method: 'POST', path: '/v1/properties', body: fields }
  }
  const id = parseUuid(request.id || '')
  if (!id) return null
  if (request.kind === 'read') return { method: 'GET', path: `/v1/properties/${id}` }
  if (request.kind === 'claims') return { method: 'GET', path: `/v1/properties/${id}/claims?limit=${limit}${cursor}` }
  if (request.kind === 'claim') {
    const statement = parseStatement(request.statement)
    if (!statement) return null
    return { method: 'POST', path: `/v1/properties/${id}/claims`, body: { statement } }
  }
  return null
}

export async function callPropertyApi({ base, token, tenantId, request, fetchImpl = fetch }) {
  if (!apiBaseAllowed(base)) throw new ApiError('unavailable')
  if (typeof token !== 'string' || token.length < 20 || token.length > 12000 || /\s/.test(token)) throw new ApiError('signin')
  if (!parseUuid(tenantId || '')) throw new ApiError('tenant')
  const resolved = resolvePropertyPath(request)
  if (!resolved) throw new ApiError('invalid')
  const url = new URL(resolved.path, base)
  if (url.origin !== new URL(base).origin) throw new ApiError('unavailable')
  const headers = {
    Accept: 'application/json',
    Authorization: `Bearer ${token}`,
    'X-Tenant-ID': tenantId,
  }
  if (resolved.body) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetchImpl(url, {
      method: resolved.method,
      headers,
      body: resolved.body ? JSON.stringify(resolved.body) : undefined,
      redirect: 'manual',
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
    })
  } catch {
    throw new ApiError('unavailable')
  }
  if (response.status >= 300 && response.status < 400) throw new ApiError('unavailable')
  const text = await response.text()
  if (text.length > 2_000_000) throw new ApiError('unavailable')
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      throw new ApiError('unavailable')
    }
  }
  if (response.status < 200 || response.status >= 300) throw new ApiError(codeForStatus(response.status))
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new ApiError('unavailable')
  return payload
}
