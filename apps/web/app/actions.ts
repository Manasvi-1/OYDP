'use server'

import { redirect } from 'next/navigation'
import { ApiError, callPropertyApi } from '../lib/api'
import { parseSessionInput, UUID } from '../lib/contract.mjs'
import { clearSession, readSession, writeSession } from '../lib/session'

function bounce(path: string, error: unknown): never {
  const message = error instanceof ApiError ? error.message : 'The property service could not complete this request'
  redirect(`${path}?error=${encodeURIComponent(message)}`)
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
  } catch (error) {
    bounce('/', error)
  }
  await writeSession(parsed.session)
  redirect('/properties')
}

export async function disconnectSession() {
  await clearSession()
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
