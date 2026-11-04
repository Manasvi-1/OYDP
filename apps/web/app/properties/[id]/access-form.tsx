'use client'

import { shareReadAccess } from '../../actions'

export function AccessForm({ propertyId }: { propertyId: string }) {
  return (
    <form className="stack" action={async (formData) => {
      const expiry = new Date(String(formData.get('expiresLocal') ?? ''))
      formData.set('expiresAt', Number.isNaN(expiry.getTime()) ? '' : expiry.toISOString())
      await shareReadAccess(propertyId, formData)
    }}>
      <label>
        Recipient subject
        <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
      </label>
      <label>
        Read access expires
        <input name="expiresLocal" type="datetime-local" required />
      </label>
      <button className="primary" type="submit">Grant read access</button>
    </form>
  )
}
