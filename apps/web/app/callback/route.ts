import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { callPropertyApi } from '../../lib/api'
import { parseSessionInput, UUID } from '../../lib/contract.mjs'
import { oidcConfig, OIDC_COOKIE, readUnverifiedStringClaim, tokenEndpoint } from '../../lib/oidc.mjs'
import { writeSession } from '../../lib/session'

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) return reject(request, config?.error ?? 'Sign-in is not configured')
  const incoming = new URL(request.url)
  const code = incoming.searchParams.get('code') ?? ''
  const state = incoming.searchParams.get('state') ?? ''
  const jar = await cookies()
  const raw = jar.get(OIDC_COOKIE)?.value
  jar.set(OIDC_COOKIE, '', { httpOnly: true, sameSite: 'lax', path: '/callback', maxAge: 0 })
  let pending: { state?: string; nonce?: string; verifier?: string } = {}
  try {
    pending = JSON.parse(raw ?? '')
  } catch {
    pending = {}
  }
  if (!code || !state || state !== pending.state || !pending.verifier || !pending.nonce) {
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
  if (!tokenResponse.ok || !accessToken || readUnverifiedStringClaim(idToken, 'nonce') !== pending.nonce) {
    return reject(request, 'Identity provider did not return a usable access token')
  }
  const tenantId = readUnverifiedStringClaim(accessToken, 'tenant_id')
  if (!UUID.test(tenantId)) {
    return reject(request, 'The access token needs a tenant_id attribute from the identity provider')
  }
  const parsed = parseSessionInput({ apiBase: config.apiBase, tenantId, accessToken })
  if (!parsed.ok) return reject(request, parsed.error)
  try {
    await callPropertyApi(parsed.session, '/v1/properties?limit=1')
  } catch (error) {
    return reject(request, error instanceof Error ? error.message : 'Property service unavailable')
  }
  await writeSession(parsed.session)
  return NextResponse.redirect(new URL('/properties', request.url))
}

function reject(request: Request, message: string) {
  return NextResponse.redirect(new URL(`/?error=${encodeURIComponent(message.slice(0, 300))}`, request.url))
}
