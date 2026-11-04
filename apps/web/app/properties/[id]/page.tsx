import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { correctProperty, recordClaim, revokeReadAccess, revokeWriteAccess } from '../../actions'
import { ApiError, callPropertyApi } from '../../../lib/api'
import { claimsQuery, correctionsQuery, UUID } from '../../../lib/contract.mjs'
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
  const error = query.error?.slice(0, 300)
  const notice = {
    'read-access-updated': 'Read access was updated.',
    'read-access-revoked': 'Read access revocation was submitted.',
    'property-corrected': 'The correction was submitted. The previous label stays in the correction history.',
    'write-access-updated': 'Write delegation was updated.',
    'write-access-revoked': 'Write delegation revocation was submitted.',
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
        </div>
        <aside className="stack">
          <section className="panel">
            <h2>Read access</h2>
            <p className="muted">Grants are read-only, expire, and can be revoked. The API allows at most 30 days.</p>
            <AccessForm propertyId={id} />
          </section>
          <section className="panel">
            <h2>Delegated writer</h2>
            <p className="muted">The recipient must already be an editor in this tenant. A writer can correct and add claims. A writer cannot share or delegate further.</p>
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

function formatWhen(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
