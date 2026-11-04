import Link from 'next/link'
import { redirect } from 'next/navigation'
import { ApiError, callPropertyApi, listLimit } from '../../lib/api'
import { errorText, parseCursor } from '../../lib/fields.mjs'
import { formatWhen, propertyPage } from '../../lib/records.mjs'
import { clearSession, readSession } from '../../lib/session'

export const dynamic = 'force-dynamic'

export default async function PropertiesPage({ searchParams }: { searchParams: Promise<{ cursor?: string; error?: string }> }) {
  const session = await readSession()
  if (!session?.tenantId) redirect('/')
  const limit = listLimit()
  const params = await searchParams
  const cursor = parseCursor(params.cursor)
  let message = errorText(params.error)
  let page = null
  if (!limit || cursor == null) {
    message = errorText('invalid')
  } else {
    try {
      page = propertyPage(await callPropertyApi(session, { kind: 'list', limit, cursor }))
      if (!page) message = errorText('unavailable')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'signin') {
        await clearSession()
        redirect('/?error=signin')
      }
      message = errorText(error instanceof ApiError ? error.code : 'unavailable')
    }
  }
  return (
    <section>
      <div className="lede">
        <h1>Properties you can read</h1>
        <p className="muted">
          The list shows records you created, or records with a current read grant. It is ordered from the newest.
          Records you cannot read are omitted, and there is no total count. A record here is not an ownership certificate.
        </p>
      </div>
      {message ? <p className="banner">{message}</p> : null}
      <div className="actions">
        <Link className="button primary" href="/properties/new">New property</Link>
      </div>
      <div className="grid">
        {page?.items.length ? page.items.map((property) => (
          <Link className="card" key={property.id} href={`/properties/${property.id}`}>
            <h2>{property.label}</h2>
            <div className="meta">
              <span>{property.jurisdiction}</span>
              <span>{formatWhen(property.createdAt)}</span>
              <span>{property.createdBy}</span>
            </div>
          </Link>
        )) : <p className="panel">No visible properties on this page.</p>}
      </div>
      {page?.nextCursor ? (
        <p className="actions">
          <Link className="button secondary" href={`/properties?cursor=${encodeURIComponent(page.nextCursor)}`}>Older properties</Link>
        </p>
      ) : null}
    </section>
  )
}
