import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { openRequest, recordClaim, saveEvidenceNote, saveIdentifier, uploadDocument } from '../../actions'
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
  let identifiers: Record<string, string>[] = []
  let evidence: Record<string, string>[] = []
  let documents: Record<string, string>[] = []
  let audit: Record<string, string>[] = []
  let requests: Record<string, string>[] = []
  try {
    property = propertyRecord(await callPropertyApi(session, { kind: 'read', id }))
    if (limit && cursor != null) {
      claims = claimPage(await callPropertyApi(session, { kind: 'claims', id, limit, cursor }))
      identifiers = textRows(await callPropertyApi(session, { kind: 'identifiers', id, limit }), ['scheme', 'identifier_value', 'superseded_at'])
      evidence = textRows(await callPropertyApi(session, { kind: 'evidence-list', id, limit }), ['assertion_text', 'review_status'])
      documents = textRows(await callPropertyApi(session, { kind: 'documents', id, limit }), ['status', 'media_type', 'rejection_code'])
      audit = textRows(await callPropertyApi(session, { kind: 'audit', id, limit }), ['event_type', 'actor_subject'])
      requests = textRows(await callPropertyApi(session, { kind: 'requests', id, limit }), ['title', 'status', 'body'])
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
      <section className="stack" aria-label="Identifiers">
        <h2>Identifiers you typed</h2>
        <p className="muted">One current value is kept for each scheme. These are not verified survey, khata, or municipal records.</p>
        {identifiers.filter((item) => !item.superseded_at).map((item) => (
          <p className="panel" key={`${item.scheme}-${item.identifier_value}`}><span className="badge">{item.scheme}</span> {item.identifier_value}</p>
        ))}
        <form className="panel stack" action={saveIdentifier.bind(null, property.id)}>
          <label>
            Scheme
            <select name="scheme" defaultValue="survey_number">
              <option value="local_label">Local label</option>
              <option value="survey_number">Survey number</option>
              <option value="khata">Khata</option>
              <option value="municipal_reference">Municipal reference</option>
            </select>
          </label>
          <label>
            Identifier
            <input name="identifier" required maxLength={200} autoComplete="off" />
          </label>
          <button className="primary" type="submit">Save identifier</button>
        </form>
      </section>
      <section className="stack" aria-label="Evidence notes">
        <h2>Evidence notes</h2>
        <p className="muted">A workspace note stays unreviewed. It is not a professional approval.</p>
        {evidence.map((item) => (
          <p className="panel" key={item.assertion_text}><span className="badge">{item.review_status}</span> {item.assertion_text}</p>
        ))}
        <form className="panel stack" action={saveEvidenceNote.bind(null, property.id)}>
          <label>
            Evidence note
            <textarea name="assertion" required maxLength={10000} />
          </label>
          <button className="primary" type="submit">Save evidence note</button>
        </form>
      </section>
      <section className="stack" aria-label="Private documents">
        <h2>Private documents</h2>
        <p className="muted">PDF, PNG, and JPEG files are encrypted after a content check. Rejected files are not stored. This is not an antivirus scan, and a read grant does not include the file.</p>
        {documents.map((item) => (
          <p className="panel" key={`${item.status}-${item.media_type}-${item.rejection_code}`}>{item.status} {item.media_type || item.rejection_code}</p>
        ))}
        <form className="panel stack" action={uploadDocument.bind(null, property.id)}>
          <label>
            Document
            <input name="document" type="file" required />
          </label>
          <button className="primary" type="submit">Upload document</button>
        </form>
      </section>
      <section className="stack" aria-label="Audit">
        <h2>Audit</h2>
        <p className="muted">Event names only. Delivery to an independent archive is not included.</p>
        {audit.map((item) => <p className="panel" key={`${item.event_type}-${item.actor_subject}`}>{item.event_type}</p>)}
      </section>
      <section className="stack" aria-label="Diligence">
        <h2>Diligence requests</h2>
        <p className="muted">A request is workspace text. It is not an offer or a legal conclusion.</p>
        {requests.map((item) => (
          <article className="panel" key={item.title}><h2>{item.title}</h2><p>{item.body}</p><span className="badge">{item.status}</span></article>
        ))}
        <form className="panel stack" action={openRequest.bind(null, property.id)}>
          <label>
            Request title
            <input name="title" required maxLength={200} />
          </label>
          <label>
            Request note
            <textarea name="requestBody" required maxLength={10000} />
          </label>
          <button className="primary" type="submit">Open request</button>
        </form>
      </section>
    </section>
  )
}

function textRows(value: unknown, keys: string[]) {
  if (!value || typeof value !== 'object' || !Array.isArray((value as { items?: unknown }).items)) return []
  return (value as { items: Record<string, unknown>[] }).items.map((item) => {
    const row: Record<string, string> = {}
    for (const key of keys) {
      const field = item[key]
      row[key] = field == null ? '' : String(field)
    }
    return row
  })
}
