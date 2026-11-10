import { cookies } from 'next/headers'
import { decodeSession, encodeSession, SESSION_COOKIE, type WorkspaceSession } from './contract.mjs'
import { cookieSecure } from './cookie-secure.mjs'
import { configuredApiBase } from './origin.mjs'

function clock() {
  return { key: process.env.SESSION_KEY, now: Math.floor(Date.now() / 1000) }
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: cookieSecure(),
    path: '/',
    maxAge,
  }
}

export async function readSession(): Promise<WorkspaceSession | null> {
  if (!configuredApiBase(process.env).ok) return null
  const jar = await cookies()
  return decodeSession(jar.get(SESSION_COOKIE)?.value, clock())
}

export async function writeSession(session: WorkspaceSession) {
  if (!configuredApiBase(process.env).ok) throw new Error('Property API origin is not configured')
  const jar = await cookies()
  jar.set(SESSION_COOKIE, encodeSession(session, clock()), cookieOptions(60 * 60 * 8))
}

export async function clearSession() {
  const jar = await cookies()
  jar.set(SESSION_COOKIE, '', cookieOptions(0))
}
