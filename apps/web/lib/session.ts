import { cookies } from 'next/headers'
import { decodeSession, encodeSession, SESSION_COOKIE, type WorkspaceSession } from './contract.mjs'

export async function readSession(): Promise<WorkspaceSession | null> {
  const jar = await cookies()
  return decodeSession(jar.get(SESSION_COOKIE)?.value)
}

export async function writeSession(session: WorkspaceSession) {
  const jar = await cookies()
  jar.set(SESSION_COOKIE, encodeSession(session), {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: 60 * 60 * 8,
  })
}

export async function clearSession() {
  const jar = await cookies()
  jar.delete(SESSION_COOKIE)
}
