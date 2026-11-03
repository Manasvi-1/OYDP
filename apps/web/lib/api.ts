import { messageFromApi, type WorkspaceSession } from './contract.mjs'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function callPropertyApi(session: WorkspaceSession, path: string, init?: { method?: string; body?: unknown }) {
  if (!path.startsWith('/v1/')) throw new ApiError(500, 'Unsupported property API path')
  let response: Response
  try {
    response = await fetch(new URL(path, session.apiBase), {
      method: init?.method ?? 'GET',
      redirect: 'manual',
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${session.accessToken}`,
        'X-Tenant-ID': session.tenantId,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: init?.body ? JSON.stringify(init.body) : undefined,
    })
  } catch {
    throw new ApiError(503, 'Property service unavailable')
  }
  if (response.status >= 300 && response.status < 400) {
    throw new ApiError(502, 'Property service refused to answer directly')
  }
  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }
  if (!response.ok) throw new ApiError(response.status, messageFromApi(response.status, payload))
  return payload
}
