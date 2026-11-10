import { redirect } from 'next/navigation'
import { connectTenant } from '../actions'
import { readPendingAuth } from '../../lib/pending-auth'
import { readSession } from '../../lib/session'
import { bounded } from '../components/format'

export const dynamic = 'force-dynamic'

export default async function TenantConnectPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await readSession()) redirect('/overview')
  const pending = await readPendingAuth()
  if (!pending) redirect('/?error=' + encodeURIComponent('Sign in again to choose a tenant'))
  const params = await searchParams
  const error = bounded(params.error)
  return (
    <div className="auth-shell">
      <section className="auth-card" aria-labelledby="tenant-title">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">OY</span>
          <div>
            <strong>OYDP</strong>
            <div className="muted">Choose a provisioned tenant</div>
          </div>
        </div>
        <h1 id="tenant-title">Confirm tenant membership</h1>
        <p className="muted">
          Sign-in succeeded. Enter the tenant UUID already provisioned for subject
          {pending.subject ? ` “${pending.subject}”` : ''}. The workspace cannot create memberships.
        </p>
        {error ? <p className="banner" role="alert">{error}</p> : null}
        <form className="stack" action={connectTenant}>
          <label>
            Tenant ID
            <input name="tenantId" required spellCheck={false} autoComplete="off" placeholder="UUID from membership provisioning" />
          </label>
          <button className="primary" type="submit">Open workspace</button>
        </form>
      </section>
    </div>
  )
}
