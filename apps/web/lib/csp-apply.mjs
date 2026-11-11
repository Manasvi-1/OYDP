import { contentSecurityPolicy, useProductionCsp } from './csp.mjs'

/** Edge-safe 32-byte nonce as standard base64. */
export function freshCspNonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  let binary = ''
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

/** Build the CSP policy and request header map for one response. */
export function buildCspEnvelope(env = process.env) {
  const nonce = freshCspNonce()
  const policy = contentSecurityPolicy(nonce, useProductionCsp(env))
  return {
    nonce,
    policy,
    requestHeaders: {
      'x-nonce': nonce,
      'Content-Security-Policy': policy,
    },
  }
}
