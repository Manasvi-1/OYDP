'use client'

import { useState, type ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import { Sidebar } from './sidebar'
import { shortId } from './format'

export function AppChrome({
  children,
  tenantId,
  signOutAction,
}: {
  children: ReactNode
  tenantId: string
  signOutAction: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()
  const crumbs = breadcrumbs(pathname)
  return (
    <div className="app-frame">
      <a className="skip-link" href="#workspace-main">Skip to content</a>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="app-main">
        <header className="app-header">
          <div className="header-actions">
            <button type="button" className="mobile-nav-toggle" aria-expanded={open} aria-controls="workspace-nav" onClick={() => setOpen((value) => !value)}>
              Menu
            </button>
            <nav className="breadcrumb" aria-label="Breadcrumb">
              <span>OYDP</span>
              {crumbs.map((crumb, index) => (
                <span key={crumb}>
                  <span aria-hidden="true">/</span>{' '}
                  {index === crumbs.length - 1 ? <strong>{crumb}</strong> : crumb}
                </span>
              ))}
            </nav>
          </div>
          <div className="header-actions">
            <span className="tenant-chip" title={tenantId}>Tenant {shortId(tenantId)}</span>
            <span className="session-chip">Authenticated session</span>
            <form action={signOutAction}>
              <button className="secondary" type="submit">Sign out</button>
            </form>
          </div>
        </header>
        <div className="content-pane" id="workspace-main">
          <p className="disclosure">
            Private workspace record. OYDP does not verify legal title, speak for a government office, guarantee valuation, or approve development.
          </p>
          {children}
        </div>
      </div>
    </div>
  )
}

function breadcrumbs(pathname: string) {
  if (pathname.startsWith('/properties/new')) return ['Properties', 'Create']
  if (pathname.startsWith('/properties/')) return ['Properties', 'Detail']
  if (pathname.startsWith('/properties')) return ['Properties']
  if (pathname.startsWith('/evidence')) return ['Evidence']
  if (pathname.startsWith('/diligence')) return ['Diligence']
  if (pathname.startsWith('/activity')) return ['Activity']
  if (pathname.startsWith('/engines')) return ['Engine directory']
  if (pathname.startsWith('/decision')) return ['Decision preview']
  if (pathname.startsWith('/settings')) return ['Settings']
  return ['Overview']
}
