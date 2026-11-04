import { createProperty } from '../../actions'
import { errorText } from '../../../lib/fields.mjs'
import { readSession } from '../../../lib/session'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

export default async function NewPropertyPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const session = await readSession()
  if (!session?.tenantId) redirect('/')
  const params = await searchParams
  const message = errorText(params.error)
  return (
    <section className="lede">
      <h1>New property candidate</h1>
      <p className="muted">
        A candidate is a private workspace record. The jurisdiction is a description you enter.
        It is not proof of coverage, a survey number, or an official identifier. Creating a record requires an access token whose methods include MFA.
      </p>
      {message ? <p className="banner">{message}</p> : null}
      <form className="panel stack" action={createProperty}>
        <label>
          Label
          <input name="label" required maxLength={200} autoComplete="off" />
        </label>
        <label>
          Jurisdiction
          <input name="jurisdiction" required maxLength={100} autoComplete="off" placeholder="Example: Bengaluru Urban" />
        </label>
        <button className="primary" type="submit">Save candidate</button>
      </form>
    </section>
  )
}
