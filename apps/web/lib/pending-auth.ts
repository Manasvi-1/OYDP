import { cookies } from 'next/headers'
import { openJson, sealJson, sessionKeyBytes } from './contract.mjs'
import { cookieSecure } from './cookie-secure.mjs'

export const PENDING_AUTH_COOKIE = 'oydp_pending_auth'
const PENDING_AAD = 'oydp-pending-auth'
const PENDING_TTL_SECONDS = 600

export type PendingAuth = {
  accessToken: string
  subject?: string
}

export async function writePendingAuth(pending: PendingAuth) {
  if (!sessionKeyBytes(process.env.SESSION_KEY)) throw new Error('Session key is not configured')
  const jar = await cookies()
  const now = Math.floor(Date.now() / 1000)
  jar.set(PENDING_AUTH_COOKIE, sealJson({
    v: 1,
    accessToken: pending.accessToken,
    subject: pending.subject ?? '',
    exp: now + PENDING_TTL_SECONDS,
  }, process.env.SESSION_KEY, PENDING_AAD), {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/',
    maxAge: PENDING_TTL_SECONDS,
  })
}

export async function readPendingAuth(): Promise<PendingAuth | null> {
  if (!sessionKeyBytes(process.env.SESSION_KEY)) return null
  const jar = await cookies()
  const now = Math.floor(Date.now() / 1000)
  const payload = openJson(jar.get(PENDING_AUTH_COOKIE)?.value, process.env.SESSION_KEY, PENDING_AAD)
  if (!payload || payload.v !== 1 || typeof payload.exp !== 'number' || payload.exp <= now) return null
  if (typeof payload.accessToken !== 'string' || !payload.accessToken.trim()) return null
  return {
    accessToken: payload.accessToken,
    subject: typeof payload.subject === 'string' ? payload.subject : undefined,
  }
}

export async function clearPendingAuth() {
  const jar = await cookies()
  jar.set(PENDING_AUTH_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/',
    maxAge: 0,
  })
}
