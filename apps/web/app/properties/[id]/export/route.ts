import { NextResponse } from 'next/server'
import { ApiError, callPropertyApi } from '../../../../lib/api'
import { UUID } from '../../../../lib/contract.mjs'
import { readSession } from '../../../../lib/session'

export const dynamic = 'force-dynamic'

const NOTICE = 'not a title certificate'

function back(request: Request, propertyId: string, message: string) {
  const url = new URL(`/properties/${propertyId}`, request.url)
  url.searchParams.set('error', message.slice(0, 300))
  return NextResponse.redirect(url, 303)
}

function stripSecrets(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripSecrets)
  if (!value || typeof value !== 'object') return value
  const clean: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (key === 'ciphertext' || key === 'nonce' || key === 'accessToken' || key === 'access_token') continue
    clean[key] = stripSecrets(item)
  }
  return clean
}

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!UUID.test(id)) return NextResponse.json({ detail: 'Property not found' }, { status: 404 })
  const session = await readSession()
  if (!session) return NextResponse.redirect(new URL('/', request.url), 303)
  let packet: unknown
  try {
    packet = await callPropertyApi(session, `/v1/properties/${id}/exports`, { method: 'POST' })
  } catch (error) {
    const message = error instanceof ApiError ? error.message : 'Property service unavailable'
    return back(request, id, message)
  }
  const record = packet && typeof packet === 'object' ? packet as { title_verified?: unknown; notice?: unknown } : null
  const notice = typeof record?.notice === 'string' ? record.notice : ''
  if (!record || record.title_verified !== false || !notice.toLowerCase().includes(NOTICE)) {
    return back(request, id, 'Property service returned an unexpected record')
  }
  const body = JSON.stringify(stripSecrets(record), null, 2)
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': 'attachment; filename="property-packet.json"',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
  })
}
