'use server'

import { redirect } from 'next/navigation'
import { ApiError, callPropertyApi, callPropertyUpload, MAX_DOCUMENT_BYTES } from '../lib/api'
import { parseSessionInput, UUID } from '../lib/contract.mjs'
import { clearPendingAuth, readPendingAuth } from '../lib/pending-auth'
import { clearSession, readSession, writeSession } from '../lib/session'

function bounce(path: string, error: unknown): never {
  const message = error instanceof ApiError ? error.message : 'The property service could not complete this request'
  const joiner = path.includes('?') ? '&' : '?'
  redirect(`${path}${joiner}error=${encodeURIComponent(message)}`)
}

export async function connectSession(formData: FormData) {
  const parsed = parseSessionInput({
    apiBase: String(formData.get('apiBase') ?? ''),
    tenantId: String(formData.get('tenantId') ?? ''),
    accessToken: String(formData.get('accessToken') ?? ''),
  })
  if (!parsed.ok) redirect(`/?error=${encodeURIComponent(parsed.error)}`)
  try {
    await callPropertyApi(parsed.session, '/v1/properties?limit=1')
    await writeSession(parsed.session)
    await clearPendingAuth()
  } catch (error) {
    bounce('/', error)
  }
  redirect('/overview')
}

export async function connectTenant(formData: FormData) {
  const pending = await readPendingAuth()
  if (!pending) redirect('/?error=' + encodeURIComponent('Sign in again to choose a tenant'))
  const parsed = parseSessionInput({
    tenantId: String(formData.get('tenantId') ?? ''),
    accessToken: pending.accessToken,
  })
  if (!parsed.ok) redirect(`/connect?error=${encodeURIComponent(parsed.error)}`)
  try {
    await callPropertyApi(parsed.session, '/v1/properties?limit=1')
    await writeSession(parsed.session)
    await clearPendingAuth()
  } catch (error) {
    bounce('/connect', error)
  }
  redirect('/overview')
}

export async function disconnectSession() {
  await clearSession()
  await clearPendingAuth()
  redirect('/')
}

export async function createProperty(formData: FormData) {
  const session = await readSession()
  if (!session) redirect('/')
  let created: { id?: string }
  try {
    created = await callPropertyApi(session, '/v1/properties', {
      method: 'POST',
      body: {
        label: String(formData.get('label') ?? ''),
        jurisdiction: String(formData.get('jurisdiction') ?? ''),
      },
    }) as { id?: string }
  } catch (error) {
    bounce('/properties/new', error)
  }
  if (!created.id || !UUID.test(created.id)) {
    redirect('/properties/new?error=' + encodeURIComponent('Property service returned an unexpected record'))
  }
  redirect(`/properties/${created.id}`)
}

export async function recordClaim(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/claims`, {
      method: 'POST',
      body: { statement: String(formData.get('statement') ?? '') },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}`)
}

export async function shareReadAccess(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const expiry = new Date(String(formData.get('expiresAt') ?? ''))
  if (Number.isNaN(expiry.getTime())) bounce(`/properties/${propertyId}`, new ApiError(422, 'Expiry must be a real date'))
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/access`, {
      method: 'PUT',
      body: {
        recipient_subject: String(formData.get('recipient') ?? ''),
        expires_at: expiry.toISOString(),
      },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=read-access-updated`)
}

export async function correctProperty(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}`, {
      method: 'PATCH',
      body: {
        label: String(formData.get('label') ?? ''),
        jurisdiction: String(formData.get('jurisdiction') ?? ''),
      },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=property-corrected`)
}

export async function grantWriteAccess(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const expiry = new Date(String(formData.get('expiresAt') ?? ''))
  if (Number.isNaN(expiry.getTime())) bounce(`/properties/${propertyId}`, new ApiError(422, 'Expiry must be a real date'))
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/writers`, {
      method: 'PUT',
      body: {
        recipient_subject: String(formData.get('recipient') ?? ''),
        expires_at: expiry.toISOString(),
      },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=write-access-updated`)
}

export async function revokeWriteAccess(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/writers`, {
      method: 'DELETE',
      body: { recipient_subject: String(formData.get('recipient') ?? '') },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=write-access-revoked`)
}

export async function revokeReadAccess(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/access`, {
      method: 'DELETE',
      body: { recipient_subject: String(formData.get('recipient') ?? '') },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=read-access-revoked`)
}

const SCHEMES = new Set(['internal', 'survey', 'municipal', 'khata'])
const ORIGINS = new Set(['user_supplied', 'professional', 'published_notice'])
const PDF = Buffer.from('%PDF-')
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
const JPEG = Buffer.from([0xff, 0xd8, 0xff])

function mediaFor(bytes: Buffer) {
  if (bytes.subarray(0, PDF.length).equals(PDF)) return 'application/pdf'
  if (bytes.subarray(0, PNG.length).equals(PNG)) return 'image/png'
  if (bytes.subarray(0, JPEG.length).equals(JPEG)) return 'image/jpeg'
  return ''
}

export async function recordIdentifier(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const scheme = String(formData.get('scheme') ?? '')
  const identifierValue = String(formData.get('identifierValue') ?? '').trim()
  const resolution = String(formData.get('resolution') ?? '')
  if (!SCHEMES.has(scheme)) bounce(`/properties/${propertyId}`, new ApiError(422, 'Invalid identifier'))
  const body: { scheme: string; identifier_value: string; resolution?: string } = {
    scheme,
    identifier_value: identifierValue,
  }
  if (resolution === 'supersede' || resolution === 'conflict') body.resolution = resolution
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/identifiers`, { method: 'POST', body })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=identifier-recorded`)
}

export async function registerSource(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const origin = String(formData.get('origin') ?? '')
  if (!ORIGINS.has(origin)) bounce(`/properties/${propertyId}`, new ApiError(422, 'Invalid source'))
  try {
    await callPropertyApi(session, '/v1/sources', {
      method: 'POST',
      body: {
        name: String(formData.get('name') ?? ''),
        origin,
        jurisdiction: String(formData.get('jurisdiction') ?? ''),
      },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=source-registered`)
}

export async function withdrawSource(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const sourceId = String(formData.get('sourceId') ?? '')
  if (!UUID.test(sourceId)) bounce(`/properties/${propertyId}`, new ApiError(422, 'Invalid source'))
  try {
    await callPropertyApi(session, `/v1/sources/${sourceId}/withdrawal`, {
      method: 'POST',
      body: { reason: String(formData.get('reason') ?? '') },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=source-withdrawn`)
}

export async function recordReview(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const disposition = String(formData.get('disposition') ?? '')
  if (disposition !== 'recorded' && disposition !== 'abstained') {
    bounce(`/properties/${propertyId}`, new ApiError(422, 'A review is recorded or abstained. It is not title.'))
  }
  const body: { disposition: string; statement: string; source_id?: string } = {
    disposition,
    statement: String(formData.get('statement') ?? ''),
  }
  const sourceId = String(formData.get('sourceId') ?? '').trim()
  if (sourceId) {
    if (!UUID.test(sourceId)) bounce(`/properties/${propertyId}`, new ApiError(422, 'Source ID must be a UUID'))
    body.source_id = sourceId
  }
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/reviews`, { method: 'POST', body })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=review-recorded`)
}

export async function grantExportConsent(propertyId: string) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/consents`, {
      method: 'POST',
      body: { purpose: 'passport_export' },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=consent-recorded`)
}

export async function revokeExportConsent(propertyId: string) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/consents`, {
      method: 'DELETE',
      body: { purpose: 'passport_export' },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=consent-revoked`)
}

export async function uploadDocument(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  const file = formData.get('document')
  if (!(file instanceof File) || file.size < 1 || file.size > MAX_DOCUMENT_BYTES) {
    bounce(`/properties/${propertyId}`, new ApiError(413, 'Document exceeds the size limit'))
  }
  const bytes = Buffer.from(await file.arrayBuffer())
  if (bytes.byteLength < 1 || bytes.byteLength > MAX_DOCUMENT_BYTES) {
    bounce(`/properties/${propertyId}`, new ApiError(413, 'Document exceeds the size limit'))
  }
  const media = mediaFor(bytes)
  if (!media) bounce(`/properties/${propertyId}`, new ApiError(422, 'Document content does not match an allowed type'))
  try {
    await callPropertyUpload(session, `/v1/properties/${propertyId}/documents`, bytes, media)
  } catch (error) {
    bounce(`/properties/${propertyId}`, error)
  }
  redirect(`/properties/${propertyId}?notice=document-quarantined`)
}

export async function openDiligenceRequest(propertyId: string, formData: FormData) {
  if (!UUID.test(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/requests`, {
      method: 'POST',
      body: {
        title: String(formData.get('title') ?? ''),
        body: String(formData.get('body') ?? ''),
      },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}?tab=diligence`, error)
  }
  redirect(`/properties/${propertyId}?tab=diligence&notice=diligence-opened`)
}

export async function addDiligenceNote(propertyId: string, requestId: string, formData: FormData) {
  if (!UUID.test(propertyId) || !UUID.test(requestId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/requests/${requestId}/notes`, {
      method: 'POST',
      body: { body: String(formData.get('body') ?? '') },
    })
  } catch (error) {
    bounce(`/properties/${propertyId}?tab=diligence`, error)
  }
  redirect(`/properties/${propertyId}?tab=diligence&notice=diligence-noted`)
}

export async function closeDiligenceRequest(propertyId: string, requestId: string) {
  if (!UUID.test(propertyId) || !UUID.test(requestId)) redirect('/properties')
  const session = await readSession()
  if (!session) redirect('/')
  try {
    await callPropertyApi(session, `/v1/properties/${propertyId}/requests/${requestId}/close`, {
      method: 'POST',
    })
  } catch (error) {
    bounce(`/properties/${propertyId}?tab=diligence`, error)
  }
  redirect(`/properties/${propertyId}?tab=diligence&notice=diligence-closed`)
}
