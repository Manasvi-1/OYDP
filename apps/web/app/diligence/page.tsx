import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { propertiesQuery, requestsQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { formatWhen } from '../components/format'
import { StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

export default async function DiligencePage() {
  const session = await readSession()
  if (!session) redirect('/')
  let error = ''
  let properties: Array<{ id: string; label: string }> = []
  try {
    const page = await callPropertyApi(session, propertiesQuery()) as { items: Array<{ id: string; label: string }> }
    properties = page.items.slice(0, 10)
  } catch (caught) {
    error = caught instanceof Error ? caught.message.slice(0, 300) : 'Property service unavailable'
  }
  const rows: Array<{
    id: string
    title: string
    status: string
    propertyId: string
    propertyLabel: string
    created_at: string
  }> = []
  for (const property of properties) {
    try {
      const page = await callPropertyApi(session, requestsQuery(property.id)) as {
        items: Array<{ id: string; title: string; status: string; created_at: string }>
      }
      for (const request of page.items) {
        rows.push({
          id: request.id,
          title: request.title,
          status: request.status,
          propertyId: property.id,
          propertyLabel: property.label,
          created_at: request.created_at,
        })
      }
    } catch {
      // Skip properties whose diligence list is unavailable.
    }
  }
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Diligence</h1>
          <p className="lede">
            Workspace diligence requests aggregated from readable properties on the first discovery page.
            These are not legally binding transactions, offers, or payments.
          </p>
        </div>
      </div>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {rows.length ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Property</th>
                <th scope="col">Status</th>
                <th scope="col">Opened</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td><Link href={`/properties/${row.propertyId}?tab=diligence`}>{row.title}</Link></td>
                  <td>{row.propertyLabel}</td>
                  <td><StatusPill label={row.status} /></td>
                  <td>{formatWhen(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <h2>No diligence requests in the current sample</h2>
          <p className="muted">Open a property detail page to create a diligence request when MFA and write rights allow it.</p>
        </div>
      )}
    </section>
  )
}
