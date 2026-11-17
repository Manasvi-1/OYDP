import { NextResponse } from 'next/server'
import { buildCspEnvelope } from './lib/csp-apply.mjs'

/**
 * Next.js 15 loads `middleware.js` (not `proxy.js`). Issues a per-request CSP
 * nonce, replaces forged caller CSP headers, and mirrors the policy on the response.
 *
 * `config.matcher` must be a static literal for the Next compiler.
 */
export function middleware(request) {
  const envelope = buildCspEnvelope()
  const headers = new Headers(request.headers)
  headers.set('x-nonce', envelope.requestHeaders['x-nonce'])
  headers.set('Content-Security-Policy', envelope.requestHeaders['Content-Security-Policy'])
  const response = NextResponse.next({ request: { headers } })
  response.headers.set('Content-Security-Policy', envelope.policy)
  response.headers.set('Cache-Control', 'no-store')
  return response
}

export const config = {
  matcher: ['/((?!api(?:/|$)|_next/static|_next/image|favicon.ico).*)'],
}
