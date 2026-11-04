'use client'

import { grantWriteAccess } from '../../actions'

export function WriterForm({ propertyId }: { propertyId: string }) {
  return (
    <form className="stack" action={async (formData) => {
      const expiry = new Date(String(formData.get('expiresLocal') ?? ''))
      formData.set('expiresAt', Number.isNaN(expiry.getTime()) ? '' : expiry.toISOString())
      await grantWriteAccess(propertyId, formData)
    }}>
      <label>
        Editor subject
        <input name="recipient" required maxLength={255} autoComplete="off" spellCheck={false} />
      </label>
      <label>
        Write access expires
        <input name="expiresLocal" type="datetime-local" required />
      </label>
      <button className="primary" type="submit">Delegate writing</button>
    </form>
  )
}
