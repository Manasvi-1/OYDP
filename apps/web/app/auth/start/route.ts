import { NextResponse, type NextRequest } from 'next/server'
import { authorizeUrl, discoveryUrl, endpointsFromDiscovery, oidcConfig, pkceChallenge } from '../../../lib/oidc.mjs'
import { seal } from '../../../lib/session-cookie.mjs'

export const dynamic = 'force-dynamic'

function target(request: NextRequest, path: string) {
  const config = oidcConfig(process.env)
  const base = config ? config.redirectUri : request.nextUrl.origin
  return new URL(path, base)
}

export async function GET(request: NextRequest) {
  const config = oidcConfig(process.env)
  const secret = process.env.SESSION_SECRET || ''
  if (!config || secret.length < 32) {
    return NextResponse.redirect(target(request, '/?error=unavailable'))
  }
  let document: unknown
  try {
    const response = await fetch(discoveryUrl(config.issuer), {
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(5000),
      headers: { Accept: 'application/json' },
    })
    if (response.status !== 200) return NextResponse.redirect(target(request, '/?error=signin'))
    document = await response.json()
  } catch {
    return NextResponse.redirect(target(request, '/?error=signin'))
  }
  const endpoints = endpointsFromDiscovery(document, config.issuer)
  if (!endpoints) return NextResponse.redirect(target(request, '/?error=signin'))
  const pkce = pkceChallenge()
  const response = NextResponse.redirect(authorizeUrl(endpoints.authorization, { ...config, ...pkce }))
  response.cookies.set('oydp_oidc', seal({ v: 1, kind: 'oidc', state: pkce.state, verifier: pkce.verifier, nonce: pkce.nonce, exp: Date.now() + 10 * 60 * 1000 }, secret), {
    httpOnly: true,
    sameSite: 'lax',
    secure: config.redirectUri.startsWith('https://'),
    path: '/',
    maxAge: 600,
  })
  response.headers.set('Cache-Control', 'no-store')
  return response
}
