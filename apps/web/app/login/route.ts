import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { sealJson, sessionKeyBytes } from '../../lib/contract.mjs'
import { cookieSecure } from '../../lib/cookie-secure.mjs'
import { authorizeRequest, oidcConfig, OIDC_AAD, OIDC_COOKIE, randomUrlToken } from '../../lib/oidc.mjs'

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) {
    const message = config?.error ?? 'Sign-in is not configured'
    return NextResponse.redirect(new URL(`/?error=${encodeURIComponent(message)}`, request.url))
  }
  if (!sessionKeyBytes(process.env.SESSION_KEY)) {
    return NextResponse.redirect(new URL('/?error=' + encodeURIComponent('Session key is not configured'), request.url))
  }
  const pending = { v: 1, state: randomUrlToken(), nonce: randomUrlToken(), verifier: randomUrlToken(), exp: Math.floor(Date.now() / 1000) + 600 }
  const jar = await cookies()
  jar.set(OIDC_COOKIE, sealJson(pending, process.env.SESSION_KEY, OIDC_AAD), {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/callback',
    maxAge: 600,
  })
  return NextResponse.redirect(authorizeRequest(config, pending))
}
