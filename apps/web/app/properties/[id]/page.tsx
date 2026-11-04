import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { recordClaim } from '../../actions'
import { ApiError, callPropertyApi, listLimit } from '../../../lib/api'
import { errorText, parseCursor, parseUuid } from '../../../lib/fields.mjs'
import { claimPage, formatWhen, propertyRecord } from '../../../lib/records.mjs'
import { clearSession, readSession } from '../../../lib/session'

export const dynamic = 'force-dynamic'

export default async function PropertyDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ claims?: string; error?: string }>
}) {
  const { id } = await params
  if (!parseUuid(id)) notFound()
  const session = await readSession()
  if (!session?.tenantId) redirect('/')
  const query = await searchParams
  const cursor = parseCursor(query.claims)
  const limit = listLimit()
  let message = errorText(query.error)
  if (!limit || cursor == null) message = errorText('invalid')
  let property = null
  let claims = null
  try {
    property = propertyRecord(await callPropertyApi(session, { kind: 'read', id }))
    if (limit && cursor != null) {
      claims = claimPage(await callPropertyApi(session, { kind: 'claims', id, limit, cursor }))
    }
    if (!property || (limit && cursor != null && !claims)) message = message || errorText('unavailable')
  } catch (error) {
    if (error instanceof ApiError && error.code === 'signin') {
      await clearSession()
      redirect('/?error=signin')
    }
    if (error instanceof ApiError && error.code === 'missing') notFound()
    message = errorText(error instanceof ApiError ? error.code : 'unavailable')
  }
  if (!property) {
    return (
      <section>
        <p><Link href="/properties">All readable properties</Link></p>
        <p className="banner">{message || errorText('unavailable')}</p>
      </section>
    )
  }
  return (
    <section>
      <p><Link href="/properties">All readable properties</Link></p>
      <div className="lede">
        <h1>{property.label}</h1>
        <div className="meta">
          <span>{property.jurisdiction}</span>
          <span>Created by {property.createdBy}</span>
          <span>{formatWhen(property.createdAt)}</span>
        </div>
        <p className="notice">
          Jurisdiction is the description stored with this candidate. It is not a coverage decision or a title finding.
        </p>
      </div>
      {message ? <p className="banner">{message}</p> : null}
      <section className="stack">
        <div>
          <h2>Unverified statements</h2>
          <p className="muted">A statement is attributed to the person who recorded it. OYDP keeps it unverified and does not treat it as evidence of ownership.</p>
        </div>
        {claims?.items.length ? claims.items.map((claim) => (
          <article className="panel stack" key={claim.id}>
            <div className="row">
              <span className="badge">{claim.status}</span>
              <span className="muted">{claim.createdBy}</span>
              <span className="muted">{formatWhen(claim.recordedAt)}</span>
            </div>
            <p className="claim">{claim.statement}</p>
          </article>
        )) : <p className="panel">No statements on this page.</p>}
        {claims?.nextCursor ? (
          <p><Link className="button secondary" href={`/properties/${property.id}?claims=${encodeURIComponent(claims.nextCursor)}`}>Older statements</Link></p>
        ) : null}
        <form className="panel stack" action={recordClaim.bind(null, property.id)}>
          <label>
            Statement
            <textarea name="statement" required maxLength={10000} placeholder="What was said, and by whom. This remains an unverified user statement." />
          </label>
          <button className="primary" type="submit">Record unverified claim</button>
        </form>
      </section>
    </section>
  )
}
