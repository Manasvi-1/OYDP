import { NextResponse } from 'next/server'
import { ApiError, callPropertyDownload } from '../../../../../lib/api'
import { UUID } from '../../../../../lib/contract.mjs'
import { readSession } from '../../../../../lib/session'

export const dynamic = 'force-dynamic'

const FILE_NAMES: Record<string, string> = {
  'application/pdf': 'document.pdf',
  'image/png': 'document.png',
  'image/jpeg': 'document.jpg',
}

function back(request: Request, propertyId: string, message: string) {
  const url = new URL(`/properties/${propertyId}`, request.url)
  url.searchParams.set('error', message.slice(0, 300))
  return NextResponse.redirect(url, 303)
}

export async function GET(request: Request, { params }: { params: Promise<{ id: string; documentId: string }> }) {
  const { id, documentId } = await params
  if (!UUID.test(id) || !UUID.test(documentId)) {
    return NextResponse.json({ detail: 'Property not found' }, { status: 404 })
  }
  const session = await readSession()
  if (!session) return NextResponse.redirect(new URL('/', request.url), 303)
  try {
    const file = await callPropertyDownload(session, `/v1/properties/${id}/documents/${documentId}/content`)
    const filename = FILE_NAMES[file.mediaType]
    if (!filename) return back(request, id, 'Document is not available')
    return new NextResponse(Buffer.from(file.bytes), {
      status: 200,
      headers: {
        'Content-Type': file.mediaType,
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      },
    })
  } catch (error) {
    const message = error instanceof ApiError ? error.message : 'Document is not available'
    return back(request, id, message)
  }
}
