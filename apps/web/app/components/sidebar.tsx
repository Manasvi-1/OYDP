'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { isActivePath, WORKSPACE_NAV } from './nav'

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname()
  return (
    <>
      {open ? <button type="button" className="sidebar-backdrop" aria-label="Close navigation" onClick={onClose} /> : null}
      <aside className={`app-sidebar${open ? ' open' : ''}`} aria-label="Workspace navigation">
        <Link className="brand-block" href="/overview" onClick={onClose}>
          <span className="brand-mark" aria-hidden="true">OY</span>
          <span className="brand-copy">
            <strong>OYDP</strong>
            <span>Property Intelligence</span>
          </span>
        </Link>
        <div>
          <p className="nav-section-label">Workspace</p>
          <ul className="nav-list">
            {WORKSPACE_NAV.map((item) => {
              const active = isActivePath(pathname, item.href)
              return (
                <li key={item.href}>
                  <Link
                    className="nav-link"
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={onClose}
                  >
                    <span>{item.label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
        <div className="sidebar-foot">
          Pre-alpha demonstration. Not a government authority. User claims are not title verification.
        </div>
      </aside>
    </>
  )
}
