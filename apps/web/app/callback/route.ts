import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { callPropertyApi } from '../../lib/api'
import { openJson, parseSessionInput, sealJson, sessionKeyBytes, UUID, encodeSession, SESSION_COOKIE } from '../../lib/contract.mjs'
import { cookieSecure } from '../../lib/cookie-secure.mjs'
import { fetchJwks, oidcConfig, OIDC_AAD, OIDC_COOKIE, tokenEndpoint, verifySignedJwt } from '../../lib/oidc.mjs'
import { PENDING_AUTH_COOKIE } from '../../lib/pending-auth'

const PENDING_AAD = 'oydp-pending-auth'
const PENDING_TTL_SECONDS = 600

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) return reject(request, config?.error ?? 'Sign-in is not configured')
  const now = Math.floor(Date.now() / 1000)
  const incoming = new URL(request.url)
  const code = incoming.searchParams.get('code') ?? ''
  const state = incoming.searchParams.get('state') ?? ''
  const jar = await cookies()
  const raw = jar.get(OIDC_COOKIE)?.value
  const pending = openJson(raw, process.env.SESSION_KEY, OIDC_AAD)
  if (!code || !state || !pending || pending.v !== 1 || state !== pending.state || typeof pending.verifier !== 'string' || typeof pending.nonce !== 'string' || typeof pending.exp !== 'number' || pending.exp <= now) {
    return finish(reject(request, 'Sign-in could not be confirmed. Start again.'))
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
    return finish(reject(request, 'Identity provider unavailable'))
  }
  if (tokenResponse.status >= 300 && tokenResponse.status < 400) {
    return finish(reject(request, 'Identity provider refused to answer directly'))
  }
  const payload = await tokenResponse.json().catch(() => null) as { access_token?: unknown; id_token?: unknown } | null
  const accessToken = typeof payload?.access_token === 'string' ? payload.access_token : ''
  const idToken = typeof payload?.id_token === 'string' ? payload.id_token : ''
  if (!tokenResponse.ok || !accessToken || !sessionKeyBytes(process.env.SESSION_KEY)) {
    return finish(reject(request, 'Identity provider did not return a usable access token'))
  }
  let jwks
  try {
    jwks = await fetchJwks(config.jwksUrl)
  } catch {
    return finish(reject(request, 'Identity provider unavailable'))
  }
  const accessCheck = verifySignedJwt(accessToken, {
    jwks,
    issuer: config.issuer,
    audience: config.audience,
    now,
    typ: 'at+jwt',
  })
  if (!accessCheck.ok) {
    return finish(reject(request, 'Identity provider did not return a usable access token'))
  }
  if (idToken) {
    const idCheck = verifySignedJwt(idToken, {
      jwks,
      issuer: config.issuer,
      audience: config.clientId,
      nonce: pending.nonce,
      now,
      typ: 'JWT',
    })
    if (!idCheck.ok) {
      return finish(reject(request, 'Identity provider did not return a usable access token'))
    }
  } else if (accessCheck.payload.nonce !== pending.nonce) {
    // Loopback issuer may bind nonce on the access token when no ID token is issued.
    return finish(reject(request, 'Identity provider did not return a usable access token'))
  }
  const tenantClaim = accessCheck.payload.tenant_id
  const tenantId = typeof tenantClaim === 'string' ? tenantClaim : ''
  const subject = typeof accessCheck.payload.sub === 'string' ? accessCheck.payload.sub : ''
  if (UUID.test(tenantId)) {
    const parsed = parseSessionInput({ tenantId, accessToken })
    if (!parsed.ok) return finish(reject(request, parsed.error))
    try {
      await callPropertyApi(parsed.session, '/v1/properties?limit=1')
    } catch (error) {
      return finish(reject(request, error instanceof Error ? error.message : 'Property service unavailable'))
    }
    const response = NextResponse.redirect(new URL('/overview', request.url))
    clearOidcCookie(response)
    response.cookies.set(SESSION_COOKIE, encodeSession(parsed.session, {
      key: process.env.SESSION_KEY,
      now,
    }), {
      httpOnly: true,
      sameSite: 'lax',
      secure: cookieSecure(),
      path: '/',
      maxAge: 60 * 60 * 8,
    })
    return response
  }
  // Return a same-origin document so the pending-auth cookie is established before
  // continuing. A second 302 after the IdP redirect can drop SameSite=Lax cookies.
  const connect = new URL('/connect', request.url).pathname
  const response = new NextResponse(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${connect}"><title>Continuing</title></head><body><a href="${connect}">Continue</a></body></html>`,
    {
      status: 200,
      headers: {
        'content-type': 'text/html; charset=utf-8',
        'cache-control': 'no-store',
      },
    },
  )
  clearOidcCookie(response)
  response.cookies.set(PENDING_AUTH_COOKIE, sealJson({
    v: 1,
    accessToken,
    subject: subject ?? '',
    exp: now + PENDING_TTL_SECONDS,
  }, process.env.SESSION_KEY, PENDING_AAD), {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/',
    maxAge: PENDING_TTL_SECONDS,
  })
  return response
}

function clearOidcCookie(response: NextResponse) {
  response.cookies.set(OIDC_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/callback',
    maxAge: 0,
  })
}

function reject(request: Request, message: string) {
  const response = NextResponse.redirect(new URL(`/?error=${encodeURIComponent(message.slice(0, 300))}`, request.url))
  clearOidcCookie(response)
  return response
}

function finish(response: NextResponse) {
  return response
}
