import Link from 'next/link'
import { redirect } from 'next/navigation'
import { readSession } from '../../lib/session'
import { StatusPill } from '../components/status-pill'

export const dynamic = 'force-dynamic'

const ENGINES = [
  {
    id: 'E01',
    name: 'Property Identity & Evidence Graph',
    status: 'Partially implemented',
    tone: 'info',
    summary: 'Private create/read/share, unverified claims, quarantined documents, identifiers, reviews, consent-gated export, and audit ledger.',
    href: '/properties',
  },
  {
    id: 'E02',
    name: 'AI Property Advisor',
    status: 'Planned',
    tone: 'planned',
    summary: 'No advisor workflow is implemented in this demonstration.',
  },
  {
    id: 'E03',
    name: 'Transaction & Legal Workspace',
    status: 'Partially implemented',
    tone: 'info',
    summary: 'Bounded diligence requests and notes only. Offers, payments, and legal conclusions remain planned.',
    href: '/diligence',
  },
  { id: 'E04', name: 'Living Property Passport', status: 'Planned', tone: 'planned', summary: 'No passport product workflow is implemented.' },
  { id: 'E05', name: 'Ownership Action Engine', status: 'Planned', tone: 'planned', summary: 'No ownership-action workflow is implemented.' },
  { id: 'E06', name: 'Real Estate Academy', status: 'Planned', tone: 'planned', summary: 'No academy content or enrollment workflow is implemented.' },
  { id: 'E07', name: 'SpatialLedger GIS Intelligence', status: 'Planned', tone: 'planned', summary: 'No GIS intelligence workflow is implemented.' },
  { id: 'E08', name: 'Property Valuation & Market Intelligence', status: 'Planned', tone: 'planned', summary: 'No valuation or market intelligence workflow is implemented.' },
  { id: 'E09', name: 'Layout & Architecture Concept Studio', status: 'Planned', tone: 'planned', summary: 'No layout studio workflow is implemented.' },
  { id: 'E10', name: 'Development & Business Feasibility', status: 'Planned', tone: 'planned', summary: 'No feasibility workflow is implemented.' },
  { id: 'E11', name: 'Marketplace & Professional Network', status: 'Planned', tone: 'planned', summary: 'No marketplace workflow is implemented.' },
  { id: 'E12', name: 'Time-Versioned Spatial Digital Twin', status: 'Planned', tone: 'planned', summary: 'No digital-twin workflow is implemented.' },
  { id: 'E13', name: 'Institutional API & Evidence Attestations', status: 'Planned', tone: 'planned', summary: 'No institutional attestation product surface is implemented.' },
] as const

export default async function EnginesPage() {
  if (!await readSession()) redirect('/')
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Engine directory</h1>
          <p className="lede">
            All 13 engines remain launch commitments. Interactive routes exist only where the active API and workspace already support them.
            Connected lifecycle today: identity → claims/documents → diligence notes → delivered audit.
          </p>
        </div>
      </div>
      <div className="engine-grid">
        {ENGINES.map((engine) => (
          <article key={engine.id} className="panel stack">
            <div className="meta">
              <span className="mono">{engine.id}</span>
              <StatusPill label={engine.status} tone={engine.tone} />
            </div>
            <h2>{engine.name}</h2>
            <p className="muted">{engine.summary}</p>
            {'href' in engine && engine.href ? (
              <p><Link className="secondary" href={engine.href}>Open live surface</Link></p>
            ) : (
              <p className="muted">No interactive module in this demo.</p>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
