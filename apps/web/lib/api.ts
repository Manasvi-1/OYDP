import { ApiError, apiBaseAllowed, callPropertyApi as call, type PropertyRequest } from './api-client.mjs'
import { pageSize } from './fields.mjs'
import type { SealedSession } from './session-cookie.mjs'

export { ApiError }

export function propertyApiBase() {
  const base = process.env.PROPERTY_API_BASE || ''
  return apiBaseAllowed(base) ? base : null
}

export function listLimit() {
  return pageSize(process.env.PROPERTY_PAGE_SIZE)
}

export async function callPropertyApi(session: SealedSession, request: PropertyRequest, tenantId = session.tenantId) {
  const base = propertyApiBase()
  if (!base || !tenantId) throw new ApiError(!base ? 'unavailable' : 'tenant')
  return call({ base, token: session.accessToken, tenantId, request })
}
