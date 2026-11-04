import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { propertiesQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'

export const dynamic = 'force-dynamic'

interface PropertyRecord {
  id: string
  label: string
  jurisdiction: string
  created_at: string
  created_by: string
}

interface PropertyPage {
  items: PropertyRecord[]
  next_cursor: string | null
}

export default async function PropertiesPage({ searchParams }: { searchParams: Promise<{ cursor?: string; error?: string }> }) {
  const session = await readSession()
  if (!session) redirect('/')
  const params = await searchParams
  let page: PropertyPage | null = null
  let error = bounded(params.error)
  try {
    page = await callPropertyApi(session, propertiesQuery(params.cursor)) as PropertyPage
  } catch (caught) {
    error = bounded(caught instanceof Error ? caught.message : 'Property service unavailable')
  }
  return (
    <section>
      <div className="lede">
        <h1>Properties you can read</h1>
        <p className="muted">Only records you created, or records with a current read grant, are listed. Nothing here is an ownership certificate.</p>
      </div>
      {error ? <p className="banner">{error}</p> : null}
      <div className="actions" style={{ marginBottom: '1rem' }}>
        <Link className="primary" href="/properties/new">New property</Link>
      </div>
      <div className="grid">
        {page?.items.length ? page.items.map((property) => (
          <Link className="card" key={property.id} href={`/properties/${property.id}`}>
            <h2>{property.label}</h2>
            <div className="meta">
              <span>{property.jurisdiction}</span>
              <span>{formatWhen(property.created_at)}</span>
            </div>
          </Link>
        )) : <p className="panel">No visible properties on this page.</p>}
      </div>
      {page?.next_cursor ? (
        <p style={{ marginTop: '1rem' }}>
          <Link className="secondary" href={`/properties?cursor=${encodeURIComponent(page.next_cursor)}`}>Older properties</Link>
        </p>
      ) : null}
    </section>
  )
}

function bounded(value: string | undefined) {
  return value ? value.slice(0, 300) : ''
}

function formatWhen(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
