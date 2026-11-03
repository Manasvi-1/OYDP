import { connectSession } from './actions'
import { readSession } from '../lib/session'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function ConnectPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await readSession()) redirect('/properties')
  const params = await searchParams
  const error = boundedMessage(params.error)
  return (
    <section className="lede">
      <h1>Open a private workspace</h1>
      <p className="muted">
        Use an access token already issued for the property API. This screen does not enroll an identity provider
        or certify ownership. Writes require a token whose authentication methods include MFA.
      </p>
      {error ? <p className="banner">{error}</p> : null}
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
