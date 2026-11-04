import { messageFromApi, type WorkspaceSession } from './contract.mjs'
import { configuredApiBase, directPropertyResponse, propertyRequestUrl } from './origin.mjs'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const DOCUMENT_MEDIA = new Set(['application/pdf', 'image/png', 'image/jpeg'])
export const MAX_DOCUMENT_BYTES = 1_048_576

async function propertyFetch(session: WorkspaceSession, path: string, init?: {
  method?: string
  body?: BodyInit
  contentType?: string
  accept?: string
}) {
  const api = configuredApiBase(process.env)
  if (!api.ok) throw new ApiError(500, api.error)
  const target = propertyRequestUrl(api.origin, path)
  if (!target) throw new ApiError(500, 'Unsupported property API path')
  let response: Response
  try {
    response = await fetch(target, {
      method: init?.method ?? 'GET',
      redirect: 'manual',
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
      headers: {
        Accept: init?.accept ?? 'application/json',
        Authorization: `Bearer ${session.accessToken}`,
        'X-Tenant-ID': session.tenantId,
        ...(init?.contentType ? { 'Content-Type': init.contentType } : {}),
      },
      body: init?.body,
    })
  } catch {
    throw new ApiError(503, 'Property service unavailable')
  }
  const decision = directPropertyResponse(response.status)
  if (!decision.ok) throw new ApiError(502, decision.error)
  return response
}

async function jsonPayload(response: Response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

export async function callPropertyApi(session: WorkspaceSession, path: string, init?: { method?: string; body?: unknown }) {
  const response = await propertyFetch(session, path, {
    method: init?.method,
    contentType: init?.body ? 'application/json' : undefined,
    body: init?.body ? JSON.stringify(init.body) : undefined,
  })
  const payload = await jsonPayload(response)
  if (!response.ok) throw new ApiError(response.status, messageFromApi(response.status, payload))
  return payload
}

export async function callPropertyUpload(session: WorkspaceSession, path: string, bytes: Uint8Array, mediaType: string) {
  if (!DOCUMENT_MEDIA.has(mediaType) || bytes.byteLength < 1 || bytes.byteLength > MAX_DOCUMENT_BYTES) {
    throw new ApiError(422, 'Document type is not allowed')
  }
  const response = await propertyFetch(session, path, {
    method: 'POST',
    contentType: mediaType,
    body: Buffer.from(bytes),
  })
  const payload = await jsonPayload(response)
  if (!response.ok) throw new ApiError(response.status, messageFromApi(response.status, payload))
  return payload
}

export async function callPropertyDownload(session: WorkspaceSession, path: string) {
  const response = await propertyFetch(session, path, {
    accept: 'application/pdf, image/png, image/jpeg, application/json',
  })
  if (!response.ok) {
    const payload = await jsonPayload(response)
    throw new ApiError(response.status, messageFromApi(response.status, payload))
  }
  const mediaType = (response.headers.get('content-type') ?? '').split(';', 1)[0].trim().toLowerCase()
  if (!DOCUMENT_MEDIA.has(mediaType)) throw new ApiError(502, 'Property service returned an unexpected record')
  const bytes = new Uint8Array(await response.arrayBuffer())
  if (bytes.byteLength < 1 || bytes.byteLength > MAX_DOCUMENT_BYTES) {
    throw new ApiError(502, 'Property service returned an unexpected record')
  }
  return { bytes, mediaType }
}
