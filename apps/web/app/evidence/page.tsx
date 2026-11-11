import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { claimsQuery, documentsQuery, propertiesQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { formatWhen } from '../components/format'
import { documentStatusLabel, StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

export default async function EvidencePage() {
  const session = await readSession()
  if (!session) redirect('/')
  let properties: Array<{ id: string; label: string }> = []
  let error = ''
  try {
    const page = await callPropertyApi(session, propertiesQuery()) as { items: Array<{ id: string; label: string }> }
    properties = page.items.slice(0, 8)
  } catch (caught) {
    error = caught instanceof Error ? caught.message.slice(0, 300) : 'Property service unavailable'
  }
  const rows: Array<{
    propertyId: string
    propertyLabel: string
    kind: string
    summary: string
    status: string
    tone?: string
    when: string
  }> = []
  for (const property of properties) {
    try {
      const claims = await callPropertyApi(session, claimsQuery(property.id)) as {
        items: Array<{ statement: string; verification_status: string; recorded_at: string }>
      }
      for (const claim of claims.items.slice(0, 3)) {
        rows.push({
          propertyId: property.id,
          propertyLabel: property.label,
          kind: 'User-submitted claim',
          summary: claim.statement,
          status: claim.verification_status,
          when: claim.recorded_at,
        })
      }
    } catch {
      // Skip unavailable claim pages.
    }
    try {
      const documents = await callPropertyApi(session, documentsQuery(property.id)) as {
        items: Array<{ media_type: string; scan_state: string; created_at: string }>
      }
      for (const document of documents.items.slice(0, 3)) {
        const status = documentStatusLabel(document.scan_state)
        rows.push({
          propertyId: property.id,
          propertyLabel: property.label,
          kind: 'Uploaded document',
          summary: document.media_type,
          status: status.label,
          tone: status.tone,
          when: document.created_at,
        })
      }
    } catch {
      // Skip unavailable document pages.
    }
  }
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Evidence</h1>
          <p className="lede">
            Cross-property view of user-submitted claims and quarantined documents from the first page of readable properties.
            No item here is government-verified ownership evidence.
          </p>
        </div>
      </div>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {rows.length ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th scope="col">Property</th>
                <th scope="col">Kind</th>
                <th scope="col">Summary</th>
                <th scope="col">Status</th>
                <th scope="col">Recorded</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.propertyId}-${row.kind}-${index}`}>
                  <td><Link href={`/properties/${row.propertyId}?tab=${row.kind === 'Uploaded document' ? 'documents' : 'claims'}`}>{row.propertyLabel}</Link></td>
                  <td>{row.kind}</td>
                  <td className="claim">{row.summary}</td>
                  <td><StatusPill label={row.status} tone={row.tone} /></td>
                  <td>{formatWhen(row.when)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <h2>No evidence in the current sample</h2>
          <p className="muted">Open a property to record an unverified claim or quarantine a document.</p>
        </div>
      )}
    </section>
  )
}
