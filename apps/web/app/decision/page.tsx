import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { claimsQuery, documentsQuery, identifiersQuery, propertiesQuery, reviewsQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

type Bucket =
  | 'Verified-by-identified-source'
  | 'User-submitted claim'
  | 'Unreviewed evidence'
  | 'Missing'
  | 'Conflicting'
  | 'Model-generated'

export default async function DecisionPage() {
  const session = await readSession()
  if (!session) redirect('/')
  let property: { id: string; label: string; jurisdiction: string } | null = null
  let error = ''
  try {
    const page = await callPropertyApi(session, propertiesQuery()) as {
      items: Array<{ id: string; label: string; jurisdiction: string }>
    }
    property = page.items[0] ?? null
  } catch (caught) {
    error = caught instanceof Error ? caught.message.slice(0, 300) : 'Property service unavailable'
  }

  const rows: Array<{ signal: string; bucket: Bucket; detail: string; tone: string }> = []
  if (property) {
    const [claims, identifiers, reviews, documents] = await Promise.all([
      safePage(session, claimsQuery(property.id)),
      safePage(session, identifiersQuery(property.id)),
      safePage(session, reviewsQuery(property.id)),
      safePage(session, documentsQuery(property.id)),
    ])
    rows.push({
      signal: 'Property label / jurisdiction',
      bucket: 'User-submitted claim',
      detail: `${property.label} · ${property.jurisdiction}`,
      tone: 'warn',
    })
    if (!claims?.items?.length) {
      rows.push({ signal: 'Ownership statement', bucket: 'Missing', detail: 'No unverified claims on the first page.', tone: 'planned' })
    } else {
      for (const claim of claims.items.slice(0, 3)) {
        rows.push({
          signal: 'User claim',
          bucket: 'User-submitted claim',
          detail: String(claim.statement ?? '').slice(0, 160),
          tone: 'warn',
        })
      }
    }
    if (!identifiers?.items?.length) {
      rows.push({ signal: 'Survey / municipal identifier', bucket: 'Missing', detail: 'No identifiers recorded on the first page.', tone: 'planned' })
    } else {
      for (const item of identifiers.items.slice(0, 3)) {
        const conflict = String(item.status) === 'conflict'
        rows.push({
          signal: `${item.scheme} identifier`,
          bucket: conflict ? 'Conflicting' : 'User-submitted claim',
          detail: `${item.identifier_value} · status ${item.status}`,
          tone: conflict ? 'danger' : 'warn',
        })
      }
    }
    if (!reviews?.items?.length) {
      rows.push({ signal: 'Professional review', bucket: 'Missing', detail: 'No reviews recorded on the first page.', tone: 'planned' })
    } else {
      for (const review of reviews.items.slice(0, 3)) {
        const cited = Boolean(review.source_id)
        rows.push({
          signal: 'Professional review',
          bucket: cited ? 'Verified-by-identified-source' : 'Unreviewed evidence',
          detail: `${review.disposition}: ${String(review.statement ?? '').slice(0, 120)} · title_effect=${review.title_effect}`,
          tone: cited ? 'info' : 'warn',
        })
      }
    }
    if (!documents?.items?.length) {
      rows.push({ signal: 'Uploaded packet', bucket: 'Missing', detail: 'No quarantined documents on the first page.', tone: 'planned' })
    } else {
      for (const document of documents.items.slice(0, 3)) {
        rows.push({
          signal: 'Uploaded document',
          bucket: 'Unreviewed evidence',
          detail: `${document.media_type} · scan_state=${document.scan_state}`,
          tone: 'warn',
        })
      }
    }
  }

  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Decision intelligence preview</h1>
          <p className="lede">
            Deterministic classification of first-page property signals. There is no model endpoint in this repository,
            so nothing here is model-generated title or ownership verification.
          </p>
        </div>
      </div>
      <p className="notice" role="status">
        Demo mode: synthetic decision buckets applied to real API payloads. OYDP does not certify title.
      </p>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {!property && !error ? (
        <div className="empty-state">
          <h2>No readable property available</h2>
          <p className="muted">Create a property first, then return for the deterministic preview.</p>
          <p><Link className="primary" href="/properties/new">Create property</Link></p>
        </div>
      ) : null}
      {property ? (
        <>
          <p className="muted">Source property: <Link href={`/properties/${property.id}`}>{property.label}</Link></p>
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Signal</th>
                  <th scope="col">Bucket</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.signal}-${index}`}>
                    <td>{row.signal}</td>
                    <td><StatusPill label={row.bucket} tone={row.tone} /></td>
                    <td className="claim">{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  )
}

async function safePage(session: NonNullable<Awaited<ReturnType<typeof readSession>>>, path: string) {
  try {
    return await callPropertyApi(session, path) as { items: Array<Record<string, unknown>> }
  } catch {
    return null
  }
}
