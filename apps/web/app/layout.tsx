import type { ReactNode } from 'react'
import { disconnectSession } from './actions'
import { AppChrome } from './components/app-chrome'
import { readSession } from '../lib/session'
import './globals.css'

export const metadata = {
  title: 'OYDP — Property Intelligence Workspace',
  description: 'Authenticated property intelligence workspace for Own Your Dream Property. Unverified claims stay labeled as such.',
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await readSession()
  return (
    <html lang="en">
      <body>
        {session ? (
          <AppChrome tenantId={session.tenantId} signOutAction={disconnectSession}>
            {children}
          </AppChrome>
        ) : children}
      </body>
    </html>
  )
}
