'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { ApiError, callPropertyApi } from '../lib/api'
import { parsePropertyInput, parseStatement, parseUuid } from '../lib/fields.mjs'
import { clearSession, readSession, writeSession } from '../lib/session'

function fail(path: string, code: string): never {
  redirect(`${path}?error=${encodeURIComponent(code)}`)
}

export async function selectTenant(formData: FormData) {
  const session = await readSession()
  if (!session) redirect('/?error=signin')
  const tenantId = String(formData.get('tenantId') ?? '')
  if (!parseUuid(tenantId)) fail('/', 'tenant')
  try {
    await callPropertyApi(session, { kind: 'list', limit: 1 }, tenantId)
  } catch (error) {
    const code = error instanceof ApiError ? error.code : 'unavailable'
    fail('/', code === 'denied' || code === 'missing' ? 'tenant' : code)
  }
  await writeSession({ ...session, tenantId })
  redirect('/properties')
}

export async function signOut() {
  await clearSession()
  redirect('/')
}

export async function createProperty(formData: FormData) {
  const session = await readSession()
  if (!session?.tenantId) redirect('/')
  const fields = parsePropertyInput(String(formData.get('label') ?? ''), String(formData.get('jurisdiction') ?? ''))
  if (!fields) fail('/properties/new', 'invalid')
  let created: { id?: unknown }
  try {
    created = await callPropertyApi(session, { kind: 'create', ...fields })
  } catch (error) {
    fail('/properties/new', error instanceof ApiError ? error.code : 'unavailable')
  }
  const id = typeof created.id === 'string' ? created.id : ''
  if (!parseUuid(id)) fail('/properties/new', 'unavailable')
  redirect(`/properties/${id}`)
}

export async function recordClaim(propertyId: string, formData: FormData) {
  if (!parseUuid(propertyId)) redirect('/properties')
  const session = await readSession()
  if (!session?.tenantId) redirect('/')
  const statement = parseStatement(String(formData.get('statement') ?? ''))
  if (!statement) fail(`/properties/${propertyId}`, 'invalid')
  try {
    await callPropertyApi(session, { kind: 'claim', id: propertyId, statement })
  } catch (error) {
    const code = error instanceof ApiError ? error.code : 'unavailable'
    if (code === 'signin') {
      await clearSession()
      redirect('/?error=signin')
    }
    fail(`/properties/${propertyId}`, code)
  }
  revalidatePath(`/properties/${propertyId}`)
  redirect(`/properties/${propertyId}?recorded=1`)
}
