import Link from 'next/link'
import { redirect } from 'next/navigation'
import { callPropertyApi } from '../../lib/api'
import { auditQuery, propertiesQuery } from '../../lib/contract.mjs'
import { readSession } from '../../lib/session'
import { formatWhen } from '../components/format'
import { StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

export default async function ActivityPage() {
  const session = await readSession()
  if (!session) redirect('/')
  let error = ''
  let properties: Array<{ id: string; label: string }> = []
  try {
    const page = await callPropertyApi(session, propertiesQuery()) as { items: Array<{ id: string; label: string }> }
    properties = page.items.slice(0, 8)
  } catch (caught) {
    error = caught instanceof Error ? caught.message.slice(0, 300) : 'Property service unavailable'
  }
  const events: Array<{
    event_type: string
    actor_subject: string
    recorded_at: string
    delivered_at: string
    propertyId: string
    propertyLabel: string
  }> = []
  for (const property of properties) {
    try {
      const page = await callPropertyApi(session, auditQuery(property.id)) as {
        items: Array<{ event_type: string; actor_subject: string; recorded_at: string; delivered_at: string }>
      }
      for (const item of page.items.slice(0, 5)) {
        events.push({ ...item, propertyId: property.id, propertyLabel: property.label })
      }
    } catch {
      // Skip unavailable audit pages.
    }
  }
  events.sort((a, b) => Date.parse(b.recorded_at) - Date.parse(a.recorded_at))
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Activity</h1>
          <p className="lede">
            Delivered audit events from readable properties. Sensitive claim text and document bytes are omitted.
            Local outbox delivery is not an immutable archival service.
          </p>
        </div>
      </div>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {events.length ? (
        <div className="panel">
          <div className="timeline">
            {events.map((event, index) => (
              <article key={`${event.propertyId}-${event.event_type}-${event.recorded_at}-${index}`} className="timeline-item">
                <div>
                  <div className="mono">{formatWhen(event.recorded_at)}</div>
                  <div className="muted">Delivered {formatWhen(event.delivered_at)}</div>
                </div>
                <div>
                  <strong>{event.event_type}</strong>
                  <div className="meta">
                    <Link href={`/properties/${event.propertyId}?tab=audit`}>{event.propertyLabel}</Link>
                    <span>Actor {event.actor_subject}</span>
                    <StatusPill label="Delivered locally" tone="info" />
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <h2>No delivered audit events in the current sample</h2>
          <p className="muted">Create or update a property to enqueue audit ledger rows.</p>
        </div>
      )}
    </section>
  )
}
