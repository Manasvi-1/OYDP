import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { correctProperty, grantExportConsent, recordClaim, recordIdentifier, recordReview, registerSource, revokeExportConsent, revokeReadAccess, revokeWriteAccess, uploadDocument, withdrawSource } from '../../actions'
import { ApiError, callPropertyApi } from '../../../lib/api'
import { auditQuery, claimsQuery, correctionsQuery, documentsQuery, identifiersQuery, reviewsQuery, sourcesQuery, UUID } from '../../../lib/contract.mjs'
import { readSession } from '../../../lib/session'
import { AccessForm } from './access-form'
import { WriterForm } from './writer-form'

export const dynamic = 'force-dynamic'

interface PropertyRecord {
  id: string
  label: string
  jurisdiction: string
  created_at: string
  created_by: string
}

interface ClaimRecord {
  id: string
  statement: string
  created_by: string
  recorded_at: string
  verification_status: string
  kind: string
}

interface ClaimPage {
  items: ClaimRecord[]
  next_cursor: string | null
}

interface CorrectionRecord {
  id: string
  previous_label: string
  label: string
  previous_jurisdiction: string
  jurisdiction: string
  actor_subject: string
  recorded_at: string
}

interface CorrectionPage {
  items: CorrectionRecord[]
  next_cursor: string | null
}

interface IdentifierRecord {
  id: string
  scheme: string
  identifier_value: string
  version: number
  status: string
  recorded_by: string
  recorded_at: string
}

interface IdentifierPage {
  items: IdentifierRecord[]
  next_cursor: string | null
}

interface ReviewRecord {
  id: string
  disposition: string
  statement: string
  title_effect: string
  recorded_at: string
  source_id: string | null
}

interface ReviewPage {
  items: ReviewRecord[]
  next_cursor: string | null
}

interface SourceRecord {
  id: string
  name: string
  origin: string
  jurisdiction: string
  rights_status: string
  withdrawn_at: string | null
}

interface SourcePage {
  items: SourceRecord[]
  next_cursor: string | null
}

interface DocumentRecord {
  id: string
  media_type: string
  byte_size: number
  scan_state: string
  created_at: string
}

interface DocumentPage {
  items: DocumentRecord[]
  next_cursor: string | null
}

interface AuditRecord {
  event_type: string
  actor_subject: string
  recorded_at: string
  delivered_at: string
}

interface AuditPage {
  items: AuditRecord[]
  next_cursor: string | null
}

export default async function PropertyPage({ params, searchParams }: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ error?: string; notice?: string; cursor?: string }>
}) {
  const session = await readSession()
  if (!session) redirect('/')
  const { id } = await params
  if (!UUID.test(id)) notFound()
  const query = await searchParams
  let property: PropertyRecord
  try {
    property = await callPropertyApi(session, `/v1/properties/${id}`) as PropertyRecord
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound()
    const message = error instanceof Error ? error.message : 'Property service unavailable'
    redirect(`/properties?error=${encodeURIComponent(message.slice(0, 300))}`)
  }
  let claims: ClaimPage | null = null
  let claimsError = ''
  let corrections: CorrectionPage | null = null
  try {
    claims = await callPropertyApi(session, claimsQuery(id, query.cursor)) as ClaimPage
  } catch (error) {
    claimsError = error instanceof Error ? error.message.slice(0, 300) : 'Claims are unavailable'
  }
  try {
    corrections = await callPropertyApi(session, correctionsQuery(id, undefined)) as CorrectionPage
  } catch {
    corrections = null
  }
  const identifiers = await loadPage<IdentifierPage>(session, identifiersQuery(id, undefined))
  const reviews = await loadPage<ReviewPage>(session, reviewsQuery(id, undefined))
  const sources = await loadPage<SourcePage>(session, sourcesQuery(undefined))
  const documents = await loadPage<DocumentPage>(session, documentsQuery(id, undefined))
  const audit = await loadPage<AuditPage>(session, auditQuery(id, undefined))
  const error = query.error?.slice(0, 300)
  const notice = {
    'read-access-updated': 'Read access was updated.',
    'read-access-revoked': 'Read access revocation was submitted.',
    'property-corrected': 'The correction was submitted. The previous label stays in the correction history.',
    'write-access-updated': 'Write delegation was updated.',
    'write-access-revoked': 'Write delegation revocation was submitted.',
    'identifier-recorded': 'The identifier was submitted. A repeated value does not create a new version.',
    'review-recorded': 'The review was recorded. A review is not title.',
    'source-registered': 'The source was registered. Its rights status stays unknown.',
    'source-withdrawn': 'The source withdrawal was submitted.',
    'consent-recorded': 'Export consent was recorded for this property.',
    'consent-revoked': 'Export consent revocation was submitted.',
    'document-quarantined': 'The file was quarantined. It cannot be downloaded until a configured scanner marks it clean.',
  }[query.notice ?? ''] ?? ''
  return (
    <section>
      <p><Link href="/properties">All visible properties</Link></p>
      <div className="lede">
        <h1>{property.label}</h1>
        <div className="meta">
          <span>{property.jurisdiction}</span>
          <span>Created {formatWhen(property.created_at)}</span>
          <span className="pill">Unverified record</span>
        </div>
      </div>
      {error ? <p className="banner">{error}</p> : null}
      {notice ? <p className="notice">{notice}</p> : null}
      <div className="workspace">
        <div className="stack">
          <article className="panel">
            <h2>Claims</h2>
            <p className="muted">Statements stay user claims with unverified status. They are not official observations.</p>
            {claimsError ? <p className="banner">{claimsError}</p> : null}
            <div className="grid">
              {claims?.items.length ? claims.items.map((claim) => (
                <article key={claim.id} className="card">
                  <p className="claim">{claim.statement}</p>
                  <div className="meta">
                    <span className="pill">{claim.verification_status}</span>
                    <span>{claim.kind}</span>
                    <span>{formatWhen(claim.recorded_at)}</span>
                  </div>
                </article>
              )) : <p className="muted">No claims on this page.</p>}
            </div>
            {claims?.next_cursor ? (
              <p><Link href={`/properties/${id}?cursor=${encodeURIComponent(claims.next_cursor)}`}>Older claims</Link></p>
            ) : null}
          </article>
          {corrections?.items.length ? (
            <article className="panel">
              <h2>Correction history</h2>
              <div className="grid">
                {corrections.items.map((correction) => (
                  <article key={correction.id} className="card">
                    <p>{correction.previous_label} to {correction.label}</p>
                    <div className="meta">
                      <span>{correction.previous_jurisdiction} to {correction.jurisdiction}</span>
                      <span>{correction.actor_subject}</span>
                      <span>{formatWhen(correction.recorded_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          ) : null}
          <form className="panel stack" action={correctProperty.bind(null, id)}>
            <h2>Correct this record</h2>
            <p className="muted">Only the owner, or an editor the owner delegated, can change the label and jurisdiction. The old values remain in the correction history.</p>
            <label>
              Label
              <input name="label" required maxLength={200} defaultValue={property.label} autoComplete="off" />
            </label>
            <label>
              Jurisdiction
              <input name="jurisdiction" required maxLength={100} defaultValue={property.jurisdiction} autoComplete="off" />
            </label>
            <button className="primary" type="submit">Save correction</button>
          </form>
          <form className="panel stack" action={recordClaim.bind(null, id)}>
            <h2>Record a claim</h2>
            <p className="muted">Statements stay user claims with unverified status. They are not official observations.</p>
            <label>
              Statement
              <textarea name="statement" required maxLength={10000} />
            </label>
            <button className="primary" type="submit">Save unverified claim</button>
          </form>
          <form className="panel stack" action={recordIdentifier.bind(null, id)}>
            <h2>Property identifier</h2>
            <p className="muted">The first value is current. The same value can be submitted again. A different value needs supersede or conflict, and the previous current value stays in the history.</p>
            <label>
              Scheme
              <select name="scheme" required defaultValue="survey">
                <option value="internal">Internal</option>
                <option value="survey">Survey</option>
                <option value="municipal">Municipal</option>
                <option value="khata">Khata</option>
              </select>
            </label>
            <label>
              Identifier
              <input name="identifierValue" required maxLength={120} autoComplete="off" />
            </label>
            <label>
              When the current value changes
              <select name="resolution" defaultValue="">
                <option value="">No change yet</option>
                <option value="supersede">Supersede the current value</option>
                <option value="conflict">Record a conflict and keep the current value</option>
              </select>
            </label>
            <button className="primary" type="submit">Save identifier</button>
            {identifiers.error ? <p className="banner">{identifiers.error}</p> : null}
            <div className="grid">
              {identifiers.value?.items.length ? identifiers.value.items.map((item) => (
                <article key={item.id} className="card">
                  <p>{item.scheme}: {item.identifier_value}</p>
                  <div className="meta">
                    <span className="pill">{item.status}</span>
                    <span>v{item.version}</span>
                    <span>{item.recorded_by}</span>
                    <span>{formatWhen(item.recorded_at)}</span>
                  </div>
                </article>
              )) : <p className="muted">No identifiers on this page.</p>}
            </div>
          </form>
          <form className="panel stack" action={recordReview.bind(null, id)}>
            <h2>Professional review</h2>
            <p className="muted">A review is recorded or abstained. It is not title, and it does not verify a claim.</p>
            <label>
              Disposition
              <select name="disposition" required defaultValue="recorded">
                <option value="recorded">Recorded</option>
                <option value="abstained">Abstained</option>
              </select>
            </label>
            <label>
              Statement
              <textarea name="statement" required maxLength={2000} />
            </label>
            <label>
              Source ID, if you are citing one
              <input name="sourceId" maxLength={36} autoComplete="off" spellCheck={false} />
            </label>
            <button className="primary" type="submit">Save review</button>
            {reviews.error ? <p className="banner">{reviews.error}</p> : null}
            <div className="grid">
              {reviews.value?.items.length ? reviews.value.items.map((item) => (
                <article key={item.id} className="card">
                  <p className="claim">{item.statement}</p>
                  <div className="meta">
                    <span className="pill">{item.disposition}</span>
                    <span>Title effect: {item.title_effect}</span>
                    <span>{formatWhen(item.recorded_at)}</span>
                  </div>
                </article>
              )) : <p className="muted">No reviews on this page.</p>}
            </div>
          </form>
          <section className="panel stack">
            <h2>Quarantined documents</h2>
            <p className="muted">Files stay quarantined until a configured scanner marks them clean. This workspace does not include a malware scanner. PDF, PNG, and JPEG files up to 1 MB are accepted, and the API checks the file bytes again.</p>
            {documents.error ? <p className="banner">{documents.error}</p> : null}
            <div className="grid">
              {documents.value?.items.length ? documents.value.items.map((item) => (
                <article key={item.id} className="card">
                  <p>{item.media_type}</p>
                  <div className="meta">
                    <span className="pill">{item.scan_state}</span>
                    <span>{item.byte_size} bytes</span>
                    <span>{formatWhen(item.created_at)}</span>
                  </div>
                  {item.scan_state === 'pass' ? (
                    <p><a href={`/properties/${id}/documents/${item.id}`}>Download clean file</a></p>
                  ) : (
                    <p className="muted">No download. The file stays quarantined until a configured scanner marks it clean.</p>
                  )}
                </article>
              )) : <p className="muted">No documents on this page.</p>}
            </div>
            <form className="stack" action={uploadDocument.bind(null, id)} encType="multipart/form-data">
              <label>
                File
                <input name="document" type="file" required accept="application/pdf,image/png,image/jpeg" />
              </label>
              <button className="primary" type="submit">Quarantine file</button>
            </form>
          </section>
          {audit.value?.items.length ? (
            <article className="panel">
              <h2>Delivered audit</h2>
              <div className="grid">
                {audit.value.items.map((item) => (
                  <article key={`${item.event_type}-${item.recorded_at}-${item.actor_subject}`} className="card">
                    <p>{item.event_type}</p>
                    <div className="meta">
                      <span>{item.actor_subject}</span>
                      <span>Recorded {formatWhen(item.recorded_at)}</span>
                      <span>Delivered {formatWhen(item.delivered_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          ) : null}
          {audit.error ? <p className="banner">{audit.error}</p> : null}
        </div>
        <aside className="stack">
          <section className="panel">
            <h2>Read access</h2>
            <p className="muted">Grants are read-only, expire, and can be revoked. The API allows at most 30 days.</p>
            <AccessForm propertyId={id} />
          </section>
          <section className="panel">
            <h2>Delegated writer</h2>
            <p className="muted">The recipient must already be an editor in this tenant. A writer can correct, add claims, record identifiers, and add reviews. A writer cannot share, delegate, consent, or export.</p>
            <WriterForm propertyId={id} />
          </section>
          <form className="panel stack" action={revokeWriteAccess.bind(null, id)}>
            <h2>Revoke write access</h2>
            <label>
              Editor subject
              <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
            </label>
            <button className="secondary" type="submit">Revoke writer</button>
          </form>
          <section className="panel stack">
            <h2>Evidence sources</h2>
            <p className="muted">A source stays rights-unknown. Withdrawing it stops later reviews from citing it.</p>
            <form className="stack" action={registerSource.bind(null, id)}>
              <label>
                Name
                <input name="name" required maxLength={200} autoComplete="off" />
              </label>
              <label>
                Origin
                <select name="origin" required defaultValue="user_supplied">
                  <option value="user_supplied">User supplied</option>
                  <option value="professional">Professional</option>
                  <option value="published_notice">Published notice</option>
                </select>
              </label>
              <label>
                Jurisdiction
                <input name="jurisdiction" required maxLength={100} autoComplete="off" />
              </label>
              <button className="primary" type="submit">Register source</button>
            </form>
            {sources.error ? <p className="banner">{sources.error}</p> : null}
            <div className="grid">
              {sources.value?.items.length ? sources.value.items.map((source) => (
                <article key={source.id} className="card">
                  <p>{source.name}</p>
                  <div className="meta">
                    <span>{source.origin}</span>
                    <span>{source.jurisdiction}</span>
                    <span className="pill">{source.rights_status}</span>
                  </div>
                  <p className="muted">{source.id}</p>
                  {source.withdrawn_at ? <p className="muted">Withdrawn {formatWhen(source.withdrawn_at)}</p> : (
                    <form className="stack" action={withdrawSource.bind(null, id)}>
                      <input type="hidden" name="sourceId" value={source.id} />
                      <label>
                        Withdrawal reason
                        <input name="reason" required maxLength={500} autoComplete="off" />
                      </label>
                      <button className="secondary" type="submit">Withdraw source</button>
                    </form>
                  )}
                </article>
              )) : <p className="muted">No sources on this page.</p>}
            </div>
          </section>
          <section className="panel stack">
            <h2>Export consent</h2>
            <p className="muted">Only the property creator can allow a packet export, and only for that purpose. The packet is not a title certificate.</p>
            <form action={grantExportConsent.bind(null, id)}>
              <button className="primary" type="submit">Allow packet export</button>
            </form>
            <form action={revokeExportConsent.bind(null, id)}>
              <button className="secondary" type="submit">Revoke export consent</button>
            </form>
            <form method="post" action={`/properties/${id}/export`}>
              <button className="secondary" type="submit">Download evidence packet</button>
            </form>
          </section>
          <form className="panel stack" action={revokeReadAccess.bind(null, id)}>
            <h2>Revoke read access</h2>
            <label>
              Recipient subject
              <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
            </label>
            <button className="secondary" type="submit">Revoke</button>
          </form>
        </aside>
      </div>
    </section>
  )
}

async function loadPage<T>(session: NonNullable<Awaited<ReturnType<typeof readSession>>>, path: string) {
  try {
    return { value: await callPropertyApi(session, path) as T, error: '' }
  } catch (error) {
    return { value: null, error: error instanceof Error ? error.message.slice(0, 300) : 'This section is unavailable' }
  }
}

function formatWhen(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
