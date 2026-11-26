import Link from 'next/link'
import { redirect } from 'next/navigation'
import { generateDedupCandidates, recordDedupReview } from '../actions'
import { callPropertyApi } from '../../lib/api'
import { dedupCandidateQuery, dedupCandidatesQuery, dedupReviewsQuery, UUID } from '../../lib/contract.mjs'
import {
  DEDUP_NOTICE,
  DEDUP_SUCCESS_NOTICE,
  dedupReviewActionLabels,
  visibleDedupReviewOutcomes,
} from '../../lib/dedup.mjs'
import { readSession } from '../../lib/session'
import { formatWhen } from '../components/format'

export const dynamic = 'force-dynamic'

interface CandidateItem {
  id: string
  property_a_id: string
  property_b_id: string
  match_basis: string
  match_scheme: string
  match_value_normalized: string
  status: string
  generated_at: string
  properties_merged: boolean
  title_effect: string
}

interface ComparisonPayload {
  candidate: CandidateItem
  property_a: {
    property_id: string
    label: string
    jurisdiction: string
    identifiers: Array<{ scheme: string; identifier_value: string; status: string }>
  }
  property_b: {
    property_id: string
    label: string
    jurisdiction: string
    identifiers: Array<{ scheme: string; identifier_value: string; status: string }>
  }
  shared_identifier_values: string[]
  properties_merged: boolean
  title_verified: boolean
  notice: string
}

interface ReviewItem {
  id: string
  outcome: string
  reason: string
  recorded_by: string
  recorded_at: string
  properties_merged: boolean
  title_effect: string
}

export default async function DedupPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const session = await readSession()
  if (!session) redirect('/')
  const params = (await searchParams) ?? {}
  const error = typeof params.error === 'string' ? params.error : ''
  const notice = typeof params.notice === 'string' ? params.notice : ''
  const selected = typeof params.candidate === 'string' && UUID.test(params.candidate)
    ? params.candidate
    : ''

  let candidates: CandidateItem[] = []
  let nextCursor: string | null = null
  let listError = ''
  let comparison: ComparisonPayload | null = null
  let reviews: ReviewItem[] = []
  let detailError = ''

  try {
    const page = await callPropertyApi(session, dedupCandidatesQuery()) as {
      items: CandidateItem[]
      next_cursor: string | null
      notice?: string
    }
    candidates = page.items
    nextCursor = page.next_cursor
  } catch (caught) {
    listError = caught instanceof Error ? caught.message.slice(0, 300) : 'Dedup service unavailable'
  }

  if (selected) {
    try {
      comparison = await callPropertyApi(session, dedupCandidateQuery(selected)) as ComparisonPayload
      const reviewPage = await callPropertyApi(session, dedupReviewsQuery(selected)) as {
        items: ReviewItem[]
      }
      reviews = reviewPage.items
    } catch (caught) {
      detailError = caught instanceof Error ? caught.message.slice(0, 300) : 'Candidate unavailable'
    }
  }

  const labels = dedupReviewActionLabels()
  const noticeText = notice === 'dedup-reviewed'
    ? DEDUP_SUCCESS_NOTICE
    : notice === 'dedup-generated'
      ? 'Candidate generation finished. Similarity is not title proof and no properties were merged.'
      : ''

  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Dedup candidates</h1>
          <p className="lede">{DEDUP_NOTICE}</p>
        </div>
        <form action={generateDedupCandidates}>
          <button type="submit" className="primary">Generate candidates</button>
        </form>
      </div>

      {error ? <p className="banner" role="alert">{error}</p> : null}
      {noticeText ? <p className="banner" role="status">{noticeText}</p> : null}
      {listError ? <p className="banner" role="alert">{listError}</p> : null}

      <div className="stack">
        <h2>Open and reviewed candidates</h2>
        {candidates.length === 0 && !listError ? (
          <p className="muted">No readable candidates yet. Generate from editable same-tenant properties.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Match</th>
                <th>Properties</th>
                <th>Status</th>
                <th>Generated</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link href={`/dedup?candidate=${item.id}`}>
                      {item.match_basis}
                      {item.match_scheme ? ` / ${item.match_scheme}` : ''}
                      {': '}
                      {item.match_value_normalized}
                    </Link>
                  </td>
                  <td>
                    <Link href={`/properties/${item.property_a_id}`}>{item.property_a_id.slice(0, 8)}</Link>
                    {' · '}
                    <Link href={`/properties/${item.property_b_id}`}>{item.property_b_id.slice(0, 8)}</Link>
                  </td>
                  <td>{item.status}</td>
                  <td>{formatWhen(item.generated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {nextCursor ? (
          <p><Link className="secondary" href={`/dedup?cursor=${encodeURIComponent(nextCursor)}`}>Older candidates</Link></p>
        ) : null}
      </div>

      {selected ? (
        <div className="stack">
          <h2>Evidence comparison</h2>
          {detailError ? <p className="banner" role="alert">{detailError}</p> : null}
          {comparison ? (
            <>
              <p className="muted">{comparison.notice}</p>
              <p className="muted">
                title_verified={String(comparison.title_verified)}; properties_merged={String(comparison.properties_merged)}
              </p>
              <div className="grid-two">
                {[comparison.property_a, comparison.property_b].map((side) => (
                  <div key={side.property_id}>
                    <h3><Link href={`/properties/${side.property_id}`}>{side.label}</Link></h3>
                    <p className="muted">{side.jurisdiction}</p>
                    <ul>
                      {side.identifiers.map((identifier) => (
                        <li key={`${identifier.scheme}-${identifier.identifier_value}-${identifier.status}`}>
                          {identifier.scheme}: {identifier.identifier_value} ({identifier.status})
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              {comparison.shared_identifier_values.length > 0 ? (
                <p>Shared identifier values: {comparison.shared_identifier_values.join(', ')}</p>
              ) : (
                <p className="muted">No shared current/conflict identifier values listed for this pair.</p>
              )}

              <h3>Human review</h3>
              <p className="muted">Reviews never merge properties or assert title.</p>
              <form action={recordDedupReview} className="stack">
                <input type="hidden" name="candidateId" value={selected} />
                <label>
                  Outcome
                  <select name="outcome" required defaultValue="keep_separate">
                    {visibleDedupReviewOutcomes().map((outcome) => (
                      <option key={outcome} value={outcome}>
                        {labels[outcome as keyof typeof labels]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Reason
                  <textarea name="reason" required maxLength={500} rows={3} />
                </label>
                <button type="submit" className="primary">Record review</button>
              </form>

              {reviews.length > 0 ? (
                <ul>
                  {reviews.map((review) => (
                    <li key={review.id}>
                      {review.outcome} by {review.recorded_by} at {formatWhen(review.recorded_at)}
                      {' — '}
                      {review.reason}
                      {' '}
                      (merged={String(review.properties_merged)}; title_effect={review.title_effect})
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No reviews recorded yet.</p>
              )}
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
