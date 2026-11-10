import { redirect } from 'next/navigation'
import { configuredApiBase } from '../../lib/origin.mjs'
import { oidcConfig } from '../../lib/oidc.mjs'
import { readSession } from '../../lib/session'
import { shortId } from '../components/format'

export const dynamic = 'force-dynamic'

export default async function SettingsPage() {
  const session = await readSession()
  if (!session) redirect('/')
  const api = configuredApiBase(process.env)
  const oidc = oidcConfig(process.env)
  return (
    <section>
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="lede">Server-configured workspace context. Secrets and tokens are never shown in the browser.</p>
        </div>
      </div>
      <div className="workspace">
        <article className="panel stack">
          <h2>Session</h2>
          <p className="muted">Access tokens stay in an encrypted httpOnly cookie. JavaScript cannot read them.</p>
          <div className="meta">
            <span className="tenant-chip">Tenant {shortId(session.tenantId)}</span>
            <span className="session-chip">Authenticated</span>
          </div>
        </article>
        <article className="panel stack">
          <h2>Service configuration</h2>
          <p><strong>Property API origin:</strong> {api.ok ? api.origin : api.error}</p>
          <p><strong>OIDC sign-in:</strong> {oidc?.ok ? 'Configured' : oidc?.error ?? 'Paste-token mode only'}</p>
          <p className="muted">Tenant memberships are provisioned out-of-band. This UI cannot create them.</p>
        </article>
      </div>
    </section>
  )
}
