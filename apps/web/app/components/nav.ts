export interface NavItem {
  href: string
  label: string
  status?: 'live' | 'planned'
  plannedLabel?: string
}

export const WORKSPACE_NAV: NavItem[] = [
  { href: '/overview', label: 'Overview' },
  { href: '/properties', label: 'Properties' },
  { href: '/evidence', label: 'Evidence' },
  { href: '/diligence', label: 'Diligence' },
  { href: '/activity', label: 'Activity' },
  { href: '/engines', label: 'Engine directory' },
  { href: '/decision', label: 'Decision preview' },
  { href: '/settings', label: 'Settings' },
]

export function isActivePath(pathname: string, href: string) {
  if (href === '/overview') return pathname === '/overview' || pathname === '/'
  if (href === '/properties') return pathname === '/properties' || pathname.startsWith('/properties/')
  return pathname === href || pathname.startsWith(`${href}/`)
}
