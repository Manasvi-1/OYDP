import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { propertiesQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { bounded, formatWhen } from '../components/format'
import { StatusPill } from '../components/status-pill'

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
      <div className="page-header">
        <div>
          <h1>Properties</h1>
          <p className="lede">Only records you created, or records with a current read grant, are listed. Nothing here is an ownership certificate.</p>
        </div>
        <div className="page-actions">
          <Link className="primary" href="/properties/new">New property</Link>
        </div>
      </div>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {page?.items.length ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">Label</th>
                <th scope="col">Jurisdiction</th>
                <th scope="col">Created</th>
                <th scope="col">Created by</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((property) => (
                <tr key={property.id}>
                  <td><Link href={`/properties/${property.id}`}>{property.label}</Link></td>
                  <td>{property.jurisdiction}</td>
                  <td>{formatWhen(property.created_at)}</td>
                  <td className="mono">{property.created_by}</td>
                  <td><StatusPill label="Unverified record" tone="warn" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <h2>No visible properties on this page</h2>
          <p className="muted">Create a private record to begin the evidence and diligence journey.</p>
          <p><Link className="primary" href="/properties/new">Create property</Link></p>
        </div>
      )}
      {page?.next_cursor ? (
        <p className="pager-row">
          <Link className="secondary" href={`/properties?cursor=${encodeURIComponent(page.next_cursor)}`}>Older properties</Link>
        </p>
      ) : null}
    </section>
  )
}
