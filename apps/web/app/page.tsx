import { connectSession } from './actions'
import { oidcConfig } from '../lib/oidc.mjs'
import { readSession } from '../lib/session'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function ConnectPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await readSession()) redirect('/properties')
  const params = await searchParams
  const error = boundedMessage(params.error)
  const signIn = oidcConfig(process.env)
  return (
    <section className="lede">
      <h1>Open a private workspace</h1>
      <p className="muted">
        Sign in through the local identity provider when it is configured. The one-time code is checked before a
        property can be created, shared, corrected, or delegated. This screen does not certify ownership.
      </p>
      {error ? <p className="banner">{error}</p> : null}
      {signIn?.ok ? <p><a className="primary" href="/login">Sign in</a></p> : null}
      {signIn && !signIn.ok ? <p className="banner">{signIn.error}</p> : null}
      <form className="panel stack" action={connectSession}>
        <label>
          API base
          <input name="apiBase" type="url" required defaultValue="http://localhost:8000" autoComplete="off" />
        </label>
        <label>
          Tenant ID
          <input name="tenantId" required spellCheck={false} autoComplete="off" placeholder="UUID from membership provisioning" />
        </label>
        <label>
          Access token
          <input name="accessToken" type="password" required autoComplete="off" spellCheck={false} />
        </label>
        <button className="primary" type="submit">Continue</button>
      </form>
    </section>
  )
}

function boundedMessage(value: string | undefined) {
  if (!value) return ''
  return value.slice(0, 300)
}
