import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { propertiesQuery, requestsQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { bounded, formatWhen } from '../components/format'
import { StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

interface PropertyRecord {
  id: string
  label: string
  jurisdiction: string
  created_at: string
}

interface PropertyPage {
  items: PropertyRecord[]
  next_cursor: string | null
}

interface RequestRecord {
  id: string
  title: string
  status: string
  property_id: string
  created_at: string
}

export default async function OverviewPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const session = await readSession()
  if (!session) redirect('/')
  const params = await searchParams
  let page: PropertyPage | null = null
  let error = bounded(params.error)
  try {
    page = await callPropertyApi(session, propertiesQuery()) as PropertyPage
  } catch (caught) {
    error = bounded(caught instanceof Error ? caught.message : 'Property service unavailable')
  }
  const recent = page?.items.slice(0, 5) ?? []
  const openDiligence: Array<RequestRecord & { propertyLabel: string }> = []
  for (const property of recent) {
    try {
      const requests = await callPropertyApi(session, requestsQuery(property.id)) as { items: RequestRecord[] }
      for (const request of requests.items.filter((item) => item.status === 'open').slice(0, 2)) {
        openDiligence.push({ ...request, propertyLabel: property.label })
      }
    } catch {
      // Diligence is optional on the overview; property list remains the source of truth.
    }
  }
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Overview</h1>
          <p className="lede">Workspace summary from records this session can already read. Counts are page-scoped, not invented portfolio totals.</p>
        </div>
        <div className="page-actions">
          <Link className="primary" href="/properties/new">New property</Link>
          <Link className="secondary" href="/properties">Browse properties</Link>
        </div>
      </div>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      <div className="metric-grid">
        <article className="metric-card">
          <div className="metric-label">Visible properties on this page</div>
          <div className="metric-value">{page ? page.items.length : '—'}</div>
          <div className="metric-note">{page?.next_cursor ? 'More pages exist beyond this sample.' : 'Derived from GET /v1/properties.'}</div>
        </article>
        <article className="metric-card">
          <div className="metric-label">Open diligence in recent sample</div>
          <div className="metric-value">{openDiligence.length}</div>
          <div className="metric-note">Checked against the first page of readable properties only.</div>
        </article>
        <article className="metric-card">
          <div className="metric-label">Title verification</div>
          <div className="metric-value metric-value-compact">Not claimed</div>
          <div className="metric-note">OYDP does not certify ownership or government status.</div>
        </article>
      </div>
      <div className="workspace">
        <section className="panel stack">
          <h2>Recent properties</h2>
          {recent.length ? (
            <div className="grid">
              {recent.map((property) => (
                <Link className="card" key={property.id} href={`/properties/${property.id}`}>
                  <h2>{property.label}</h2>
                  <div className="meta">
                    <span>{property.jurisdiction}</span>
                    <span>{formatWhen(property.created_at)}</span>
                    <StatusPill label="Unverified record" tone="warn" />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <h2>No readable properties yet</h2>
              <p className="muted">Create a private candidate or obtain a same-tenant read grant.</p>
              <p><Link className="primary" href="/properties/new">Create property</Link></p>
            </div>
          )}
        </section>
        <aside className="stack">
          <section className="panel stack">
            <h2>Quick actions</h2>
            <Link className="secondary" href="/properties/new">Create property record</Link>
            <Link className="secondary" href="/diligence">Review diligence requests</Link>
            <Link className="secondary" href="/engines">Open engine directory</Link>
            <Link className="secondary" href="/activity">Inspect delivered audit</Link>
          </section>
          <section className="panel stack">
            <h2>Pending diligence</h2>
            {openDiligence.length ? openDiligence.map((item) => (
              <article key={item.id} className="card">
                <h2>{item.title}</h2>
                <div className="meta">
                  <span>{item.propertyLabel}</span>
                  <StatusPill label={item.status} />
                  <span>{formatWhen(item.created_at)}</span>
                </div>
                <p><Link href={`/properties/${item.property_id}?tab=diligence`}>Open request</Link></p>
              </article>
            )) : <p className="muted">No open diligence found in the recent property sample.</p>}
          </section>
        </aside>
      </div>
    </section>
  )
}
