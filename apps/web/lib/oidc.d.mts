export const OIDC_COOKIE: string
export const OIDC_AAD: string

export interface OidcPending {
  state: string
  nonce: string
  verifier: string
  exp?: number
  v?: number
}

export interface JsonWebKeySet {
  keys: Array<Record<string, unknown>>
}

export type OidcConfig =
  | null
  | { ok: false; error: string }
  | {
      ok: true
      issuer: string
      clientId: string
      redirectUri: string
      apiBase: string
      jwksUrl: string
      audience: string
    }

export type VerifiedJwt =
  | { ok: true; payload: Record<string, unknown> }
  | { ok: false; error: string }

export function randomUrlToken(bytes?: number): string
export function codeChallenge(verifier: string): string
export function oidcConfig(env: Record<string, string | undefined>): OidcConfig
export function authorizeRequest(config: Exclude<OidcConfig, null | { ok: false }>, pending: OidcPending): URL
export function tokenEndpoint(config: Exclude<OidcConfig, null | { ok: false }>): string
export function verifySignedJwt(token: string | undefined, options: {
  jwks: JsonWebKeySet
  issuer: string
  audience: string
  now: number
  typ: string
  nonce?: string
}): VerifiedJwt
export function fetchJwks(url: string): Promise<JsonWebKeySet>
