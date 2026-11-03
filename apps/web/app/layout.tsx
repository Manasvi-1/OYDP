import type { ReactNode } from 'react'
import { disconnectSession } from './actions'
import { readSession } from '../lib/session'
import './globals.css'

export const metadata = {
  title: 'OYDP workspace',
  description: 'Private property workspace for Own Your Dream Property. Unverified claims are labeled as such.',
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await readSession()
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="shell">
            <a className="brand" href={session ? '/properties' : '/'}>
              <strong>OYDP</strong>
              <span>Own Your Dream Property</span>
            </a>
            {session ? (
              <form action={disconnectSession}>
                <button type="submit">End session</button>
              </form>
            ) : null}
          </div>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  )
}
