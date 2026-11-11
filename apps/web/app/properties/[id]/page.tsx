import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import {
  addDiligenceNote,
  closeDiligenceRequest,
  correctProperty,
  grantExportConsent,
  openDiligenceRequest,
  recordClaim,
  recordIdentifier,
  recordReview,
  registerSource,
  revokeExportConsent,
  revokeReadAccess,
  revokeWriteAccess,
  uploadDocument,
  withdrawSource,
} from '../../actions'
import { ApiError, callPropertyApi } from '../../../lib/api'
import {
  auditQuery,
  claimsQuery,
  correctionsQuery,
  documentsQuery,
  evidenceConflictsQuery,
  evidenceGraphQuery,
  identifiersQuery,
  notesQuery,
  requestsQuery,
  reviewsQuery,
  sourcesQuery,
  UUID,
} from '../../../lib/contract.mjs'
import { readSession } from '../../../lib/session'
import { bounded, formatWhen } from '../../components/format'
import { documentStatusLabel, StatusPill } from '../../components/status-pill'
import { AccessForm } from './access-form'
import { normalizeTab, PropertyTabs } from './tabs'
import { WriterForm } from './writer-form'

export const dynamic = 'force-dynamic'

interface PropertyRecord {
  id: string
  label: string
  jurisdiction: string
  created_at: string
  created_by: string
}

interface PageResult<T> {
  items: T[]
  next_cursor: string | null
}

type LoadedPage<T> = { value: T | null; error: string }

interface ClaimItem {
  id: string
  statement: string
  created_by: string
  recorded_at: string
  verification_status: string
  kind: string
}

interface CorrectionItem {
  id: string
  previous_label: string
  label: string
  previous_jurisdiction: string
  jurisdiction: string
  actor_subject: string
  recorded_at: string
}

interface IdentifierItem {
  id: string
  scheme: string
  identifier_value: string
  version: number
  status: string
  recorded_by: string
  recorded_at: string
}

interface ReviewItem {
  id: string
  statement: string
  disposition: string
  title_effect: string
  recorded_at: string
}

interface SourceItem {
  id: string
  name: string
  origin: string
  jurisdiction: string
  rights_status: string
  withdrawn_at: string | null
}

interface DocumentItem {
  id: string
  media_type: string
  byte_size: number
  scan_state: string
  created_at: string
}

interface AuditItem {
  event_type: string
  actor_subject: string
  recorded_at: string
  delivered_at: string
}

interface RequestItem {
  id: string
  title: string
  body: string
  status: string
  created_by: string
  created_at: string
  closed_at: string | null
}

interface EvidenceGraphEdge {
  from_kind: string
  from_id: string
  to_kind: string
  to_id: string
  relation: string
}

interface EvidenceGraphPayload {
  property_id: string
  title_verified: boolean
  notice: string
  edges: EvidenceGraphEdge[]
}

interface IdentifierConflictItem {
  id: string
  scheme: string
  identifier_value: string
  version: number
  status: string
  recorded_at: string
}

interface EvidenceConflictsPayload {
  property_id: string
  title_verified: boolean
  notice: string
  unresolved: boolean
  open_unverified_claim_count: number
  open_unverified_claim_ids: string[]
  multiple_open_unverified_claims: boolean
  identifier_conflicts: IdentifierConflictItem[]
  claims_citing_withdrawn_sources: string[]
}

export default async function PropertyPage({ params, searchParams }: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ error?: string; notice?: string; cursor?: string; tab?: string }>
}) {
  const session = await readSession()
  if (!session) redirect('/')
  const { id } = await params
  if (!UUID.test(id)) notFound()
  const query = await searchParams
  const tab = normalizeTab(query.tab)
  let property: PropertyRecord
  try {
    property = await callPropertyApi(session, `/v1/properties/${id}`) as PropertyRecord
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound()
    const message = error instanceof Error ? error.message : 'Property service unavailable'
    redirect(`/properties?error=${encodeURIComponent(message.slice(0, 300))}`)
  }

  const claims = await loadPage<PageResult<ClaimItem>>(session, claimsQuery(id, query.cursor))
  const corrections = await loadPage<PageResult<CorrectionItem>>(session, correctionsQuery(id, undefined))
  const identifiers = await loadPage<PageResult<IdentifierItem>>(session, identifiersQuery(id, undefined))
  const reviews = await loadPage<PageResult<ReviewItem>>(session, reviewsQuery(id, undefined))
  const sources = await loadPage<PageResult<SourceItem>>(session, sourcesQuery(undefined))
  const documents = await loadPage<PageResult<DocumentItem>>(session, documentsQuery(id, undefined))
  const audit = await loadPage<PageResult<AuditItem>>(session, auditQuery(id, undefined))
  const requests = await loadPage<PageResult<RequestItem>>(session, requestsQuery(id, undefined))
  const evidenceGraph = tab === 'graph'
    ? await loadPage<EvidenceGraphPayload>(session, evidenceGraphQuery(id))
    : { value: null, error: '' }
  const evidenceConflicts = tab === 'graph'
    ? await loadPage<EvidenceConflictsPayload>(session, evidenceConflictsQuery(id))
    : { value: null, error: '' }

  const notice = {
    'read-access-updated': 'Read access was updated.',
    'read-access-revoked': 'Read access revocation was submitted.',
    'property-corrected': 'The correction was submitted. The previous label stays in the correction history.',
    'write-access-updated': 'Write delegation was updated.',
    'write-access-revoked': 'Write delegation revocation was submitted.',
    'claim-recorded': 'The claim was recorded as unverified. It is not ownership evidence.',
    'identifier-recorded': 'The identifier was submitted. A repeated value does not create a new version.',
    'review-recorded': 'The review was recorded. A review is not title.',
    'source-registered': 'The source was registered. Its rights status stays unknown.',
    'source-withdrawn': 'The source withdrawal was submitted.',
    'consent-recorded': 'Export consent was recorded for this property.',
    'consent-revoked': 'Export consent revocation was submitted.',
    'document-quarantined': 'The file was quarantined. Download stays blocked until a configured scanner marks it clean.',
    'diligence-opened': 'Diligence request opened. This is not an offer, payment, or legal agreement.',
    'diligence-noted': 'Diligence note recorded for authorized readers.',
    'diligence-closed': 'Diligence request closed. Closed means workspace status only.',
  }[query.notice ?? ''] ?? ''

  return (
    <section>
      <p><Link href="/properties">All readable properties</Link></p>
      <div className="page-header">
        <div>
          <h1>{property.label}</h1>
          <div className="meta">
            <span>{property.jurisdiction}</span>
            <span>Created {formatWhen(property.created_at)}</span>
            <span className="mono">{property.created_by}</span>
            <StatusPill label="Unverified record" tone="warn" />
          </div>
          <p className="lede lede-follow">
            User-entered identifiers and claims are not official government verification.
          </p>
        </div>
      </div>
      {bounded(query.error) ? <p className="banner" role="alert">{bounded(query.error)}</p> : null}
      {notice ? <p className="notice" role="status">{notice}</p> : null}
      <PropertyTabs propertyId={id} active={tab} />
      {tab === 'overview' ? (
        <OverviewTab
          property={property}
          claimsCount={claims.value?.items.length ?? 0}
          documentsCount={documents.value?.items.length ?? 0}
          openRequests={(requests.value?.items ?? []).filter((item) => item.status === 'open').length}
        />
      ) : null}
      {tab === 'identity' ? <IdentityTab propertyId={id} property={property} corrections={corrections} /> : null}
      {tab === 'identifiers' ? <IdentifiersTab propertyId={id} identifiers={identifiers} /> : null}
      {tab === 'claims' ? <ClaimsTab propertyId={id} claims={claims} reviews={reviews} sources={sources} /> : null}
      {tab === 'graph' ? <GraphTab graph={evidenceGraph} conflicts={evidenceConflicts} /> : null}
      {tab === 'documents' ? <DocumentsTab propertyId={id} documents={documents} /> : null}
      {tab === 'access' ? <AccessTab propertyId={id} /> : null}
      {tab === 'diligence' ? <DiligenceTab propertyId={id} session={session} requests={requests} /> : null}
      {tab === 'audit' ? <AuditTab audit={audit} /> : null}
    </section>
  )
}

function OverviewTab({ property, claimsCount, documentsCount, openRequests }: {
  property: PropertyRecord
  claimsCount: number
  documentsCount: number
  openRequests: number
}) {
  return (
    <div className="metric-grid">
      <article className="metric-card">
        <div className="metric-label">Jurisdiction</div>
        <div className="metric-value metric-value-detail">{property.jurisdiction}</div>
        <div className="metric-note">User-entered. Not a cadastral confirmation.</div>
      </article>
      <article className="metric-card">
        <div className="metric-label">Claims on this page</div>
        <div className="metric-value">{claimsCount}</div>
        <div className="metric-note">Unverified user statements only.</div>
      </article>
      <article className="metric-card">
        <div className="metric-label">Documents on this page</div>
        <div className="metric-value">{documentsCount}</div>
        <div className="metric-note">Encrypted quarantine until a real scanner passes.</div>
      </article>
      <article className="metric-card">
        <div className="metric-label">Open diligence</div>
        <div className="metric-value">{openRequests}</div>
        <div className="metric-note">Workspace requests, not legal transactions.</div>
      </article>
    </div>
  )
}

function IdentityTab({ propertyId, property, corrections }: {
  propertyId: string
  property: PropertyRecord
  corrections: LoadedPage<PageResult<CorrectionItem>>
}) {
  return (
    <div className="workspace">
      <div className="stack">
        <article className="panel">
          <h2>Identity summary</h2>
          <p className="muted">Private candidate metadata. Corrections keep prior values in history.</p>
          <div className="meta">
            <span>Label: {property.label}</span>
            <span>Jurisdiction: {property.jurisdiction}</span>
            <span>Created {formatWhen(property.created_at)}</span>
          </div>
        </article>
        {corrections.value?.items?.length ? (
          <article className="panel">
            <h2>Correction history</h2>
            <div className="grid">
              {corrections.value.items.map((correction) => (
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
      </div>
      <form className="panel stack" action={correctProperty.bind(null, propertyId)}>
        <h2>Correct this record</h2>
        <p className="muted">Only the owner, or an editor the owner delegated, can change the label and jurisdiction.</p>
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
    </div>
  )
}

function IdentifiersTab({ propertyId, identifiers }: { propertyId: string; identifiers: LoadedPage<PageResult<IdentifierItem>> }) {
  return (
    <div className="workspace">
      <section className="panel stack">
        <h2>Recorded identifiers</h2>
        <p className="muted">Identifiers are user-entered. They are not official government verification.</p>
        {identifiers.error ? <p className="banner">{identifiers.error}</p> : null}
        <div className="grid">
          {identifiers.value?.items?.length ? identifiers.value.items.map((item) => (
            <article key={item.id} className="card">
              <p>{item.scheme}: {item.identifier_value}</p>
              <div className="meta">
                <StatusPill label={item.status} />
                <span>v{item.version}</span>
                <span>{item.recorded_by}</span>
                <span>{formatWhen(item.recorded_at)}</span>
              </div>
            </article>
          )) : <p className="muted">No identifiers on this page.</p>}
        </div>
      </section>
      <form className="panel stack" action={recordIdentifier.bind(null, propertyId)}>
        <h2>Property identifier</h2>
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
      </form>
    </div>
  )
}

function ClaimsTab({ propertyId, claims, reviews, sources }: {
  propertyId: string
  claims: LoadedPage<PageResult<ClaimItem>>
  reviews: LoadedPage<PageResult<ReviewItem>>
  sources: LoadedPage<PageResult<SourceItem>>
}) {
  return (
    <div className="workspace">
      <div className="stack">
        <article className="panel stack" aria-labelledby="claims-heading">
          <h2 id="claims-heading">User-submitted claims</h2>
          <p className="muted">Statements stay user claims with unverified status. They are not official observations or ownership evidence.</p>
          {claims.error ? <p className="banner">{claims.error}</p> : null}
          <div className="grid">
            {claims.value?.items?.length ? claims.value.items.map((claim) => (
              <article key={claim.id} className="card">
                <p className="claim">{claim.statement}</p>
                <div className="meta">
                  <StatusPill label={claim.verification_status} />
                  <span>{claim.kind}</span>
                  <span>{formatWhen(claim.recorded_at)}</span>
                </div>
              </article>
            )) : <p className="muted">No claims on this page.</p>}
          </div>
          {claims.value?.next_cursor ? (
            <p><Link href={`/properties/${propertyId}?tab=claims&cursor=${encodeURIComponent(claims.value.next_cursor)}`}>Older claims</Link></p>
          ) : null}
        </article>
        <article className="panel stack">
          <h2>Professional reviews</h2>
          <p className="muted">A review is recorded or abstained. It is not title, and it does not verify a claim.</p>
          {reviews.error ? <p className="banner">{reviews.error}</p> : null}
          <div className="grid">
            {reviews.value?.items?.length ? reviews.value.items.map((item) => (
              <article key={item.id} className="card">
                <p className="claim">{item.statement}</p>
                <div className="meta">
                  <StatusPill label={item.disposition} />
                  <span>Title effect: {item.title_effect}</span>
                  <span>{formatWhen(item.recorded_at)}</span>
                </div>
              </article>
            )) : <p className="muted">No reviews on this page.</p>}
          </div>
        </article>
      </div>
      <aside className="stack">
        <form className="panel stack" action={recordClaim.bind(null, propertyId)}>
          <h2>Record a claim</h2>
          <label>
            Claim statement
            <textarea name="statement" required maxLength={10000} aria-label="Claim statement" />
          </label>
          <button className="primary" type="submit">Record unverified claim</button>
        </form>
        <form className="panel stack" action={recordReview.bind(null, propertyId)}>
          <h2>Professional review</h2>
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
        </form>
        <section className="panel stack">
          <h2>Evidence sources</h2>
          <p className="muted">A source stays rights-unknown. Withdrawing it stops later reviews from citing it.</p>
          <form className="stack" action={registerSource.bind(null, propertyId)}>
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
            {sources.value?.items?.length ? sources.value.items.map((source) => (
              <article key={source.id} className="card">
                <p>{source.name}</p>
                <div className="meta">
                  <span>{source.origin}</span>
                  <span>{source.jurisdiction}</span>
                  <StatusPill label={source.rights_status} />
                </div>
                <p className="muted mono">{source.id}</p>
                {source.withdrawn_at ? <p className="muted">Withdrawn {formatWhen(source.withdrawn_at)}</p> : (
                  <form className="stack" action={withdrawSource.bind(null, propertyId)}>
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
      </aside>
    </div>
  )
}

function DocumentsTab({ propertyId, documents }: { propertyId: string; documents: LoadedPage<PageResult<DocumentItem>> }) {
  return (
    <section className="panel stack" aria-label="Private documents">
      <h2>Private documents</h2>
      <p className="muted">
        Uploaded files are encrypted and quarantined. This workspace has no malware scanner configured.
        Statuses stay truthful: quarantined, rejected, or available for authorized download only when the backend scan state is pass.
      </p>
      {documents.error ? <p className="banner">{documents.error}</p> : null}
      <div className="grid">
        {documents.value?.items?.length ? documents.value.items.map((item) => {
          const status = documentStatusLabel(item.scan_state)
          return (
            <article key={item.id} className="card">
              <p>{item.media_type}</p>
              <div className="meta">
                <StatusPill label={status.label} tone={status.tone} />
                <span>{item.byte_size} bytes</span>
                <span>{formatWhen(item.created_at)}</span>
              </div>
              {item.scan_state === 'pass' ? (
                <p><a href={`/properties/${propertyId}/documents/${item.id}`}>Download authorized file</a></p>
              ) : (
                <p className="muted">No download. The API blocks content until scan_state is pass.</p>
              )}
            </article>
          )
        }) : <p className="muted">No documents on this page.</p>}
      </div>
      <form className="stack" action={uploadDocument.bind(null, propertyId)} encType="multipart/form-data">
        <label>
          File
          <input name="document" type="file" required accept="application/pdf,image/png,image/jpeg" />
        </label>
        <button className="primary" type="submit">Upload document</button>
      </form>
    </section>
  )
}

function AccessTab({ propertyId }: { propertyId: string }) {
  return (
    <div className="workspace">
      <section className="panel stack">
        <h2>Read access</h2>
        <p className="muted">Grants are read-only, expire, and can be revoked. The API allows at most 30 days.</p>
        <AccessForm propertyId={propertyId} />
      </section>
      <aside className="stack">
        <section className="panel">
          <h2>Delegated writer</h2>
          <p className="muted">The recipient must already be an editor in this tenant. A writer cannot share, delegate, consent, or export.</p>
          <WriterForm propertyId={propertyId} />
        </section>
        <form className="panel stack" action={revokeWriteAccess.bind(null, propertyId)}>
          <h2>Revoke write access</h2>
          <label>
            Editor subject
            <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
          </label>
          <button className="secondary" type="submit">Revoke writer</button>
        </form>
        <form className="panel stack" action={revokeReadAccess.bind(null, propertyId)}>
          <h2>Revoke read access</h2>
          <label>
            Recipient subject
            <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
          </label>
          <button className="secondary" type="submit">Revoke</button>
        </form>
        <section className="panel stack">
          <h2>Export consent</h2>
          <p className="muted">Only the property creator can allow a packet export. The packet is not a title certificate.</p>
          <form action={grantExportConsent.bind(null, propertyId)}>
            <button className="primary" type="submit">Allow packet export</button>
          </form>
          <form action={revokeExportConsent.bind(null, propertyId)}>
            <button className="secondary" type="submit">Revoke export consent</button>
          </form>
          <form method="post" action={`/properties/${propertyId}/export`}>
            <button className="secondary" type="submit">Download evidence packet</button>
          </form>
        </section>
      </aside>
    </div>
  )
}

async function DiligenceTab({ propertyId, session, requests }: {
  propertyId: string
  session: NonNullable<Awaited<ReturnType<typeof readSession>>>
  requests: LoadedPage<PageResult<RequestItem>>
}) {
  const notesByRequest = new Map<string, Array<{ id: string; body: string; created_by: string; created_at: string }>>()
  for (const request of requests.value?.items ?? []) {
    try {
      const notes = await callPropertyApi(session, notesQuery(propertyId, request.id)) as PageResult<{
        id: string
        body: string
        created_by: string
        created_at: string
      }>
      notesByRequest.set(request.id, notes.items)
    } catch {
      notesByRequest.set(request.id, [])
    }
  }
  return (
    <div className="workspace">
      <section className="panel stack" aria-label="Diligence">
        <h2>Diligence requests</h2>
        <p className="muted">
          Diligence notes are workspace commentary for people who can already read the property.
          They are not offers, payments, legal agreements, or notifications.
        </p>
        {requests.error ? <p className="banner">{requests.error}</p> : null}
        <div className="stack">
          {requests.value?.items?.length ? requests.value.items.map((request) => (
            <article key={request.id} className="card stack">
              <h2>{request.title}</h2>
              <p className="claim">{request.body}</p>
              <div className="meta">
                <StatusPill label={request.status} />
                <span>{request.created_by}</span>
                <span>{formatWhen(request.created_at)}</span>
                {request.closed_at ? <span>Closed {formatWhen(request.closed_at)}</span> : null}
              </div>
              <div className="stack">
                <h3 className="section-title">Notes</h3>
                {(notesByRequest.get(request.id) ?? []).length ? (notesByRequest.get(request.id) ?? []).map((note) => (
                  <article key={note.id} className="panel">
                    <p className="claim">{note.body}</p>
                    <div className="meta">
                      <span>{note.created_by}</span>
                      <span>{formatWhen(note.created_at)}</span>
                    </div>
                  </article>
                )) : <p className="muted">No notes yet.</p>}
              </div>
              {request.status === 'open' ? (
                <>
                  <form className="stack" action={addDiligenceNote.bind(null, propertyId, request.id)}>
                    <label>
                      Request note
                      <textarea name="body" required maxLength={10000} aria-label="Request note" />
                    </label>
                    <button className="secondary" type="submit">Add note</button>
                  </form>
                  <form action={closeDiligenceRequest.bind(null, propertyId, request.id)}>
                    <button className="secondary" type="submit">Close request</button>
                  </form>
                </>
              ) : null}
            </article>
          )) : <p className="muted">No diligence requests on this property.</p>}
        </div>
      </section>
      <form className="panel stack" action={openDiligenceRequest.bind(null, propertyId)}>
        <h2>Open request</h2>
        <p className="muted">Creator/editor with MFA can open a request. Readers can add notes while it stays open.</p>
        <label>
          Request title
          <input name="title" required maxLength={200} autoComplete="off" aria-label="Request title" />
        </label>
        <label>
          Request note
          <textarea name="body" required maxLength={10000} aria-label="Request note" />
        </label>
        <button className="primary" type="submit">Open request</button>
      </form>
    </div>
  )
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}

function GraphTab({ graph, conflicts }: {
  graph: LoadedPage<EvidenceGraphPayload>
  conflicts: LoadedPage<EvidenceConflictsPayload>
}) {
  const conflictBody = conflicts.value
  const graphBody = graph.value
  return (
    <div className="workspace">
      <div className="stack">
        <article className="panel stack" aria-labelledby="conflicts-heading">
          <h2 id="conflicts-heading">Unresolved evidence signals</h2>
          <p className="muted">
            Server-side signals only. This is not title verification, and unresolved signals are not adjudication.
          </p>
          {conflicts.error ? <p className="banner" role="alert">{conflicts.error}</p> : null}
          {!conflicts.error && !conflictBody ? <p className="muted">Conflict signals are still loading.</p> : null}
          {conflictBody ? (
            <>
              <div className="meta">
                <StatusPill
                  label={conflictBody.title_verified ? 'Title claim present' : 'Not a title certificate'}
                  tone={conflictBody.title_verified ? 'danger' : 'warn'}
                />
                <StatusPill
                  label={conflictBody.unresolved ? 'Unresolved signals' : 'No unresolved signals'}
                  tone={conflictBody.unresolved ? 'warn' : 'ok'}
                />
                <span>{conflictBody.open_unverified_claim_count} open unverified claim(s)</span>
              </div>
              <p className="muted">{conflictBody.notice}</p>
              {conflictBody.multiple_open_unverified_claims ? (
                <p className="notice" role="status">
                  Multiple open unverified claims exist. They remain user claims and are not ranked or resolved here.
                </p>
              ) : null}
              {conflictBody.open_unverified_claim_ids.length ? (
                <div className="stack">
                  <h3>Open unverified claim IDs</h3>
                  <div className="meta">
                    {conflictBody.open_unverified_claim_ids.map((claimId) => (
                      <span key={claimId} className="mono">{shortId(claimId)}</span>
                    ))}
                  </div>
                </div>
              ) : <p className="muted">No open unverified claims.</p>}
              {conflictBody.identifier_conflicts.length ? (
                <div className="stack">
                  <h3>Identifier conflict rows</h3>
                  <div className="grid">
                    {conflictBody.identifier_conflicts.map((item) => (
                      <article key={item.id} className="card">
                        <div className="meta">
                          <StatusPill label={item.status} tone="warn" />
                          <span>{item.scheme}</span>
                          <span className="mono">{item.identifier_value}</span>
                          <span>v{item.version}</span>
                        </div>
                        <p className="muted">Conflict status is not ownership proof. Recorded {formatWhen(item.recorded_at)}.</p>
                      </article>
                    ))}
                  </div>
                </div>
              ) : <p className="muted">No identifier conflict rows.</p>}
              {conflictBody.claims_citing_withdrawn_sources.length ? (
                <div className="stack">
                  <h3>Claims citing withdrawn sources</h3>
                  <div className="meta">
                    {conflictBody.claims_citing_withdrawn_sources.map((claimId) => (
                      <span key={claimId} className="mono">{shortId(claimId)}</span>
                    ))}
                  </div>
                </div>
              ) : <p className="muted">No claims currently cite a withdrawn source.</p>}
            </>
          ) : null}
        </article>

        <article className="panel stack" aria-labelledby="graph-heading">
          <h2 id="graph-heading">Attribution edges</h2>
          <p className="muted">
            Read-only projection of existing claim, document, and review citations. Authorization is enforced by the API.
          </p>
          {graph.error ? <p className="banner" role="alert">{graph.error}</p> : null}
          {!graph.error && !graphBody ? <p className="muted">Evidence graph is still loading.</p> : null}
          {graphBody ? (
            <>
              <div className="meta">
                <StatusPill
                  label={graphBody.title_verified ? 'Title claim present' : 'Not a title certificate'}
                  tone={graphBody.title_verified ? 'danger' : 'warn'}
                />
                <span>{graphBody.edges.length} edge(s)</span>
              </div>
              <p className="muted">{graphBody.notice}</p>
              {graphBody.edges.length ? (
                <div className="grid">
                  {graphBody.edges.map((edge) => (
                    <article key={`${edge.from_kind}-${edge.from_id}-${edge.relation}-${edge.to_kind}-${edge.to_id}`} className="card">
                      <div className="meta">
                        <span>{edge.from_kind}</span>
                        <span className="mono">{shortId(edge.from_id)}</span>
                        <span>{edge.relation}</span>
                        <span>{edge.to_kind}</span>
                        <span className="mono">{shortId(edge.to_id)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : <p className="muted">No attribution edges on this property yet.</p>}
            </>
          ) : null}
        </article>
      </div>
    </div>
  )
}

function AuditTab({ audit }: { audit: LoadedPage<PageResult<AuditItem>> }) {
  return (
    <section className="panel stack" aria-label="Audit">
      <h2>Delivered audit timeline</h2>
      <p className="muted">
        Events come from the property audit ledger after local outbox delivery.
        This is not an immutable archival service.
      </p>
      {audit.error ? <p className="banner">{audit.error}</p> : null}
      <div className="timeline">
        {audit.value?.items?.length ? audit.value.items.map((item, index) => (
          <article key={`${item.event_type}-${item.recorded_at}-${item.actor_subject}-${index}`} className="timeline-item">
            <div>
              <div className="mono">{formatWhen(item.recorded_at)}</div>
              <div className="muted">Delivered {formatWhen(item.delivered_at)}</div>
            </div>
            <div>
              <strong>{item.event_type}</strong>
              <div className="meta">
                <span>Actor {item.actor_subject}</span>
                <StatusPill label="Delivered locally" tone="info" />
              </div>
            </div>
          </article>
        )) : <p className="muted">No delivered audit events on this page.</p>}
      </div>
    </section>
  )
}

async function loadPage<T>(session: NonNullable<Awaited<ReturnType<typeof readSession>>>, path: string): Promise<LoadedPage<T>> {
  try {
    return { value: await callPropertyApi(session, path) as T, error: '' }
  } catch (error) {
    return { value: null, error: error instanceof Error ? error.message.slice(0, 300) : 'This section is unavailable' }
  }
}
