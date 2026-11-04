import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { authorizeRequest, oidcConfig, OIDC_COOKIE, randomUrlToken } from '../../lib/oidc.mjs'

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) {
    const message = config?.error ?? 'Sign-in is not configured'
    return NextResponse.redirect(new URL(`/?error=${encodeURIComponent(message)}`, request.url))
  }
  const pending = { state: randomUrlToken(), nonce: randomUrlToken(), verifier: randomUrlToken() }
  const jar = await cookies()
  jar.set(OIDC_COOKIE, JSON.stringify(pending), {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/callback',
    maxAge: 600,
  })
  return NextResponse.redirect(authorizeRequest(config, pending))
}
