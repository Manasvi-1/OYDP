import { NextResponse } from 'next/server'
import { oidcTransactionCookie } from '../../lib/auth-callback.mjs'
import { sealJson, sessionKeyBytes } from '../../lib/contract.mjs'
import { cookieSecure } from '../../lib/cookie-secure.mjs'
import { authorizeRequest, oidcConfig, OIDC_AAD, randomUrlToken } from '../../lib/oidc.mjs'

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) return redirectError(config?.error ?? 'Sign-in is not configured')
  if (!sessionKeyBytes(process.env.SESSION_KEY)) return redirectError('Session key is not configured')
  const pending = {
    v: 1,
    state: randomUrlToken(),
    nonce: randomUrlToken(),
    verifier: randomUrlToken(),
    exp: Math.floor(Date.now() / 1000) + 600,
  }
  const response = NextResponse.redirect(authorizeRequest(config, pending))
  const cookie = oidcTransactionCookie(sealJson(pending, process.env.SESSION_KEY, OIDC_AAD), cookieSecure())
  response.cookies.set(cookie.name, cookie.value, {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookie.options.secure,
    path: cookie.options.path,
    maxAge: cookie.options.maxAge,
  })
  response.headers.set('cache-control', 'no-store')
  response.headers.set('referrer-policy', 'no-referrer')
  return response
}

function redirectError(message: string) {
  const response = new NextResponse(null, {
    status: 307,
    headers: { Location: `/?error=${encodeURIComponent(message.slice(0, 300))}` },
  })
  response.headers.set('cache-control', 'no-store')
  response.headers.set('referrer-policy', 'no-referrer')
  return response
}
