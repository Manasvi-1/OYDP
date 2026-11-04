import { selectTenant } from './actions'
import { errorText } from '../lib/fields.mjs'
import { readSession } from '../lib/session'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function HomePage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const session = await readSession()
  if (session?.tenantId) redirect('/properties')
  const params = await searchParams
  const message = errorText(params.error)
  if (!session) {
    return (
      <section className="lede">
        <h1>Open a private workspace</h1>
        <p className="muted">
          Sign in through the configured OpenID provider. The property API checks the access token.
          This screen does not certify ownership, title, or a government record.
        </p>
        {message ? <p className="banner">{message}</p> : null}
        <p><a className="button primary" href="/auth/start">Sign in</a></p>
      </section>
    )
  }
  return (
    <section className="lede">
      <h1>Choose the provisioned tenant</h1>
      <p className="muted">
        Signed in as {session.sub}. Membership is provisioned by an administrator. Entering an ID asks the API;
        it does not create a tenancy.
      </p>
      {message ? <p className="banner">{message}</p> : null}
      <form className="panel stack" action={selectTenant}>
        <label>
          Tenant ID
          <input name="tenantId" required spellCheck={false} autoComplete="off" placeholder="UUID from membership provisioning" />
        </label>
        <button className="primary" type="submit">Open workspace</button>
      </form>
    </section>
  )
}
