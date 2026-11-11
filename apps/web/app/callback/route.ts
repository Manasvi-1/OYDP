import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { callPropertyApi } from '../../lib/api'
import {
  beginCallback,
  callbackFailure,
  CONNECT_BRIDGE_HTML,
  finishCallback,
} from '../../lib/auth-callback.mjs'
import { openJson, parseSessionInput } from '../../lib/contract.mjs'
import { cookieSecure } from '../../lib/cookie-secure.mjs'
import { fetchJwks, oidcConfig, OIDC_AAD, OIDC_COOKIE, tokenEndpoint } from '../../lib/oidc.mjs'

type AuthCookie = {
  name: string
  value: string
  options: {
    secure: boolean
    path: string
    maxAge: number
  }
}

type AuthDecision = {
  kind?: string
  location?: string | null
  html?: string | null
  cookies?: AuthCookie[]
}

export async function GET(request: Request) {
  const config = oidcConfig(process.env)
  if (!config?.ok) return rejectUnconfigured(config?.error ?? 'Sign-in is not configured')
  const now = Math.floor(Date.now() / 1000)
  const secure = cookieSecure()
  const incoming = new URL(request.url)
  const code = incoming.searchParams.get('code') ?? ''
  const state = incoming.searchParams.get('state') ?? ''
  const jar = await cookies()
  const pending = openJson(jar.get(OIDC_COOKIE)?.value, process.env.SESSION_KEY, OIDC_AAD)
  const started = beginCallback({
    redirectUri: config.redirectUri,
    requestUrl: request.url,
    now,
    code,
    state,
    pending,
    secure,
  })
  if (started.done) return applyDecision(started.decision)

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
        code_verifier: started.verifier,
      }),
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(8000),
    })
  } catch {
    return applyDecision(callbackFailure(config.redirectUri, secure, 'unavailable'))
  }
  if (tokenResponse.status >= 300 && tokenResponse.status < 400) {
    return applyDecision(callbackFailure(config.redirectUri, secure, 'redirected'))
  }
  const payload = await tokenResponse.json().catch(() => null) as { access_token?: unknown; id_token?: unknown } | null
  const accessToken = typeof payload?.access_token === 'string' ? payload.access_token : ''
  const idToken = typeof payload?.id_token === 'string' ? payload.id_token : ''
  if (!tokenResponse.ok || !accessToken) {
    return applyDecision(callbackFailure(config.redirectUri, secure, 'unusable'))
  }
  let jwks
  try {
    jwks = await fetchJwks(config.jwksUrl)
  } catch {
    return applyDecision(callbackFailure(config.redirectUri, secure, 'unavailable'))
  }
  const exchange = { ok: true, accessToken, idToken }
  const verified = finishCallback({
    redirectUri: config.redirectUri,
    now,
    pending,
    secure,
    sessionKey: process.env.SESSION_KEY,
    issuer: config.issuer,
    audience: config.audience,
    clientId: config.clientId,
    exchange,
    jwks,
  })
  if (verified.done) return applyDecision(verified.decision)
  const parsed = parseSessionInput({ tenantId: verified.tenantId, accessToken: verified.accessToken })
  if (!parsed.ok) return applyDecision(callbackFailure(config.redirectUri, secure, 'unusable'))
  try {
    await callPropertyApi(parsed.session, '/v1/properties?limit=1')
  } catch {
    return applyDecision(finishCallback({
      redirectUri: config.redirectUri,
      now,
      pending,
      secure,
      sessionKey: process.env.SESSION_KEY,
      issuer: config.issuer,
      audience: config.audience,
      clientId: config.clientId,
      exchange,
      jwks,
      propertyAccepted: false,
    }).decision)
  }
  const accepted = finishCallback({
    redirectUri: config.redirectUri,
    now,
    pending,
    secure,
    sessionKey: process.env.SESSION_KEY,
    issuer: config.issuer,
    audience: config.audience,
    clientId: config.clientId,
    exchange,
    jwks,
    propertyAccepted: true,
  })
  if (!accepted.done || !accepted.decision) return applyDecision(callbackFailure(config.redirectUri, secure, 'unusable'))
  return applyDecision(accepted.decision)
}

function rejectUnconfigured(message: string) {
  const response = new NextResponse(null, {
    status: 307,
    headers: { Location: `/?error=${encodeURIComponent(message.slice(0, 300))}` },
  })
  response.cookies.set(OIDC_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: cookieSecure(),
    path: '/callback',
    maxAge: 0,
  })
  return harden(response)
}

function applyDecision(decision: AuthDecision | null | undefined) {
  if (!decision || (decision.kind !== 'bridge' && decision.kind !== 'redirect')) {
    return rejectUnconfigured('Sign-in could not be confirmed. Start again.')
  }
  if (decision.kind === 'bridge') {
    const response = new NextResponse(decision.html ?? CONNECT_BRIDGE_HTML, {
      status: 200,
      headers: { 'content-type': 'text/html; charset=utf-8' },
    })
    return withCookies(response, decision.cookies ?? [])
  }
  const response = new NextResponse(null, {
    status: 307,
    headers: { Location: decision.location ?? '/?error=Sign-in%20could%20not%20be%20confirmed.%20Start%20again.' },
  })
  return withCookies(response, decision.cookies ?? [])
}

function withCookies(response: NextResponse, cookiesToSet: AuthCookie[]) {
  for (const cookie of cookiesToSet) {
    response.cookies.set(cookie.name, cookie.value, {
      httpOnly: true,
      sameSite: 'lax',
      secure: cookie.options.secure,
      path: cookie.options.path,
      maxAge: cookie.options.maxAge,
    })
  }
  return harden(response)
}

function harden(response: NextResponse) {
  response.headers.set('cache-control', 'no-store')
  response.headers.set('referrer-policy', 'no-referrer')
  response.headers.set('x-content-type-options', 'nosniff')
  return response
}
