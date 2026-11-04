export interface OidcSettings {
  issuer: string
  clientId: string
  redirectUri: string
  audience: string
}

export interface Pkce {
  state: string
  nonce: string
  verifier: string
  challenge: string
}

export interface OidcEndpoints {
  authorization: string
  token: string
  jwks: string
}

export function endpointAllowed(value: string, devFlag: string): boolean
export function oidcConfig(env: Record<string, string | undefined>): OidcSettings | null
export function discoveryUrl(issuer: string): string
export function pkceChallenge(): Pkce
export function sameState(left: string | null, right: string | null): boolean
export function endpointsFromDiscovery(document: unknown, issuer: string): OidcEndpoints | null
export function authorizeUrl(endpoint: string, input: OidcSettings & Pkce): string
export function accessTokenFromResponse(payload: unknown): string | null
export function verifyAccessToken(token: string, jwks: { keys?: unknown[] }, options: { issuer: string; audience: string; now?: number }): { sub: string; exp: number; amr: string[] }
export function idTokenNonceMatches(idToken: string, nonce: string): boolean
