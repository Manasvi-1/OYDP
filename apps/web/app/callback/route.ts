import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { callPropertyApi } from '../../lib/api'
import { openJson, parseSessionInput, sessionKeyBytes, UUID } from '../../lib/contract.mjs'
import { fetchJwks, oidcConfig, OIDC_AAD, OIDC_COOKIE, tokenEndpoint, verifySignedJwt } from '../../lib/oidc.mjs'
import { writeSession } from '../../lib/session'

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) return reject(request, config?.error ?? 'Sign-in is not configured')
  const now = Math.floor(Date.now() / 1000)
  const incoming = new URL(request.url)
  const code = incoming.searchParams.get('code') ?? ''
  const state = incoming.searchParams.get('state') ?? ''
  const jar = await cookies()
  const raw = jar.get(OIDC_COOKIE)?.value
  jar.set(OIDC_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/callback',
    maxAge: 0,
  })
  const pending = openJson(raw, process.env.SESSION_KEY, OIDC_AAD)
  if (!code || !state || !pending || pending.v !== 1 || state !== pending.state || typeof pending.verifier !== 'string' || typeof pending.nonce !== 'string' || typeof pending.exp !== 'number' || pending.exp <= now) {
    return reject(request, 'Sign-in could not be confirmed. Start again.')
  }
  let tokenResponse: Response
  try {
    tokenResponse = await fetch(tokenEndpoint(config), {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: config.redirectUri,
        client_id: config.clientId,
        code_verifier: pending.verifier,
      }),
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(8000),
    })
  } catch {
    return reject(request, 'Identity provider unavailable')
  }
  if (tokenResponse.status >= 300 && tokenResponse.status < 400) {
    return reject(request, 'Identity provider refused to answer directly')
  }
  const payload = await tokenResponse.json().catch(() => null) as { access_token?: unknown; id_token?: unknown } | null
  const accessToken = typeof payload?.access_token === 'string' ? payload.access_token : ''
  const idToken = typeof payload?.id_token === 'string' ? payload.id_token : ''
  if (!tokenResponse.ok || !accessToken || !idToken || !sessionKeyBytes(process.env.SESSION_KEY)) {
    return reject(request, 'Identity provider did not return a usable access token')
  }
  let jwks
  try {
    jwks = await fetchJwks(config.jwksUrl)
  } catch {
    return reject(request, 'Identity provider unavailable')
  }
  const idCheck = verifySignedJwt(idToken, {
    jwks,
    issuer: config.issuer,
    audience: config.clientId,
    nonce: pending.nonce,
    now,
    typ: 'JWT',
  })
  const accessCheck = verifySignedJwt(accessToken, {
    jwks,
    issuer: config.issuer,
    audience: config.audience,
    now,
    typ: 'at+jwt',
  })
  const tenantClaim = accessCheck.ok ? accessCheck.payload.tenant_id : ''
  const tenantId = typeof tenantClaim === 'string' ? tenantClaim : ''
  if (!idCheck.ok || !accessCheck.ok || !UUID.test(tenantId)) {
    return reject(request, 'Identity provider did not return a usable access token')
  }
  const parsed = parseSessionInput({ tenantId, accessToken })
  if (!parsed.ok) return reject(request, parsed.error)
  try {
    await callPropertyApi(parsed.session, '/v1/properties?limit=1')
    await writeSession(parsed.session)
  } catch (error) {
    return reject(request, error instanceof Error ? error.message : 'Property service unavailable')
  }
  return NextResponse.redirect(new URL('/properties', request.url))
}

function reject(request: Request, message: string) {
  return NextResponse.redirect(new URL(`/?error=${encodeURIComponent(message.slice(0, 300))}`, request.url))
}
