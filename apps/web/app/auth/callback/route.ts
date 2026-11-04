import { NextResponse, type NextRequest } from 'next/server'
import { accessTokenFromResponse, discoveryUrl, endpointsFromDiscovery, idTokenNonceMatches, oidcConfig, sameState, verifyAccessToken } from '../../../lib/oidc.mjs'
import { asOidcTransaction, open, seal } from '../../../lib/session-cookie.mjs'

export const dynamic = 'force-dynamic'

function target(config: { redirectUri: string } | null, request: NextRequest, path: string) {
  return new URL(path, config ? config.redirectUri : request.nextUrl.origin)
}

export async function GET(request: NextRequest) {
  const config = oidcConfig(process.env)
  const secret = process.env.SESSION_SECRET || ''
  const fail = (code: string) => NextResponse.redirect(target(config, request, `/?error=${code}`))
  if (!config || secret.length < 32) return fail('unavailable')
  const code = request.nextUrl.searchParams.get('code') || ''
  const state = request.nextUrl.searchParams.get('state') || ''
  const txn = asOidcTransaction(open(request.cookies.get('oydp_oidc')?.value, secret))
  if (!txn || !sameState(txn.state, state) || code.length < 10 || code.length > 512) return fail('signin')
  let endpoints
  try {
    const discovery = await fetch(discoveryUrl(config.issuer), {
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(5000),
      headers: { Accept: 'application/json' },
    })
    if (discovery.status !== 200) return fail('signin')
    endpoints = endpointsFromDiscovery(await discovery.json(), config.issuer)
    if (!endpoints) return fail('signin')
    const exchanged = await fetch(endpoints.token, {
      method: 'POST',
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(5000),
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: config.redirectUri,
        client_id: config.clientId,
        code_verifier: txn.verifier,
      }),
    })
    if (exchanged.status !== 200) return fail('signin')
    const payload = await exchanged.json()
    const accessToken = accessTokenFromResponse(payload)
    if (!accessToken) return fail('signin')
    if (payload.id_token && !idTokenNonceMatches(payload.id_token, txn.nonce)) return fail('signin')
    const jwks = await fetch(endpoints.jwks, {
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(5000),
      headers: { Accept: 'application/json' },
    })
    if (jwks.status !== 200) return fail('signin')
    const claims = verifyAccessToken(accessToken, await jwks.json(), { issuer: config.issuer, audience: config.audience })
    const response = NextResponse.redirect(target(config, request, '/'))
    response.cookies.set('oydp_session', seal({
      v: 1,
      kind: 'session',
      accessToken,
      tenantId: null,
      sub: claims.sub,
      exp: claims.exp * 1000,
    }, secret), {
      httpOnly: true,
      sameSite: 'lax',
      secure: config.redirectUri.startsWith('https://'),
      path: '/',
      maxAge: Math.max(1, claims.exp - Math.floor(Date.now() / 1000)),
    })
    response.cookies.set('oydp_oidc', '', { httpOnly: true, sameSite: 'lax', secure: config.redirectUri.startsWith('https://'), path: '/', maxAge: 0 })
    response.headers.set('Cache-Control', 'no-store')
    return response
  } catch {
    return fail('signin')
  }
}
