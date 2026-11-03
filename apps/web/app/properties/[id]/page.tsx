import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { recordClaim, revokeReadAccess } from '../../actions'
import { ApiError, callPropertyApi } from '../../../lib/api'
import { claimsQuery, UUID } from '../../../lib/contract.mjs'
import { readSession } from '../../../lib/session'
import { AccessForm } from './access-form'

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
  try {
    claims = await callPropertyApi(session, claimsQuery(id, query.cursor)) as ClaimPage
  } catch (error) {
    claimsError = error instanceof Error ? error.message.slice(0, 300) : 'Claims are unavailable'
  }
  const error = query.error?.slice(0, 300)
  const notice = query.notice === 'read-access-updated'
    ? 'Read access was updated.'
    : query.notice === 'read-access-revoked'
      ? 'Read access revocation was submitted.'
      : ''
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
          <form className="panel stack" action={recordClaim.bind(null, id)}>
            <h2>Record a claim</h2>
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
