import Link from 'next/link'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'identity', label: 'Identity' },
  { id: 'identifiers', label: 'Identifiers' },
  { id: 'claims', label: 'Claims / evidence' },
  { id: 'documents', label: 'Documents' },
  { id: 'access', label: 'Access / sharing' },
  { id: 'diligence', label: 'Diligence' },
  { id: 'audit', label: 'Audit' },
] as const

export type PropertyTab = typeof TABS[number]['id']

export function normalizeTab(value: string | undefined): PropertyTab {
  return TABS.some((tab) => tab.id === value) ? value as PropertyTab : 'overview'
}

export function PropertyTabs({ propertyId, active }: { propertyId: string; active: PropertyTab }) {
  return (
    <nav className="tabs" aria-label="Property sections">
      {TABS.map((tab) => (
        <Link
          key={tab.id}
          className="tab"
          href={`/properties/${propertyId}?tab=${tab.id}`}
          aria-current={active === tab.id ? 'page' : undefined}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  )
}
