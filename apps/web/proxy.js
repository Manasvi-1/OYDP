import {randomBytes} from 'node:crypto';
import {NextResponse} from 'next/server';
import {contentSecurityPolicy} from './lib/csp.mjs';

export function proxy(request) {
  const nonce = randomBytes(32).toString('base64');
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === 'development');
  const headers = new Headers(request.headers);
  // Always replace caller-supplied values before the renderer sees them.
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', policy);
  const response = NextResponse.next({request:{headers}});
  response.headers.set('Content-Security-Policy', policy);
  response.headers.set('Cache-Control', 'no-store');
  return response;
}

export const config = {matcher:['/((?!api(?:/|$)|_next/static|_next/image|favicon.ico).*)']};
