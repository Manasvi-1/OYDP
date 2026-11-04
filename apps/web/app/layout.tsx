import type { Metadata } from 'next'
import { signOut } from './actions'
import { readSession } from '../lib/session'
import './globals.css'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'OYDP workspace',
  description: 'Private pre-alpha property workspace. Claims stay unverified user statements.',
  robots: { index: false, follow: false },
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await readSession()
  return (
    <html lang="en">
      <body>
        <header className="top">
          <div>
            <p className="mark">OYDP</p>
            <p className="mark-note">Pre-alpha property workspace</p>
          </div>
          {session ? (
            <form action={signOut}>
              <button className="ghost" type="submit">Sign out {session.sub}</button>
            </form>
          ) : null}
        </header>
        <main>{children}</main>
      </body>
    </html>
  )
}
