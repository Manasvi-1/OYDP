import { cookies } from 'next/headers'
import { asSession, open, seal, type SealedSession } from './session-cookie.mjs'

const COOKIE = 'oydp_session'

function secret() {
  const value = process.env.SESSION_SECRET
  return value && value.length >= 32 && value.length <= 200 ? value : null
}

function secureCookie() {
  return (process.env.OIDC_REDIRECT_URI || '').startsWith('https://')
}

export async function readSession(): Promise<SealedSession | null> {
  const key = secret()
  if (!key) return null
  const jar = await cookies()
  return asSession(open(jar.get(COOKIE)?.value, key))
}

export async function writeSession(session: SealedSession) {
  const key = secret()
  if (!key) throw new Error('SESSION_SECRET missing')
  const jar = await cookies()
  jar.set(COOKIE, seal({ ...session, v: 1, kind: 'session' }, key), {
    httpOnly: true,
    sameSite: 'lax',
    secure: secureCookie(),
    path: '/',
    maxAge: Math.max(1, Math.floor((session.exp - Date.now()) / 1000)),
  })
}

export async function clearSession() {
  const jar = await cookies()
  jar.set(COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: secureCookie(),
    path: '/',
    maxAge: 0,
  })
}
