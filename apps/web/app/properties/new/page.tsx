import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createProperty } from '../../actions'
import { readSession } from '../../../lib/session'

export const dynamic = 'force-dynamic'

export default async function NewPropertyPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (!await readSession()) redirect('/')
  const params = await searchParams
  const error = params.error?.slice(0, 300)
  return (
    <section className="lede">
      <h1>Create a property record</h1>
      <p className="muted">A label and jurisdiction start a private record. They do not verify title, survey the plot, or connect a government portal.</p>
      {error ? <p className="banner">{error}</p> : null}
      <form className="panel stack" action={createProperty}>
        <label>
          Label
          <input name="label" required maxLength={200} autoComplete="off" />
        </label>
        <label>
          Jurisdiction
          <input name="jurisdiction" required maxLength={100} autoComplete="off" placeholder="Example: Bengaluru Urban" />
        </label>
        <div className="actions">
          <button className="primary" type="submit">Create</button>
          <Link className="secondary" href="/properties">Cancel</Link>
        </div>
      </form>
    </section>
  )
}
