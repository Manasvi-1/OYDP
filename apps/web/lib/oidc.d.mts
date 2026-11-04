export const OIDC_COOKIE: string

export interface OidcPending {
  state: string
  nonce: string
  verifier: string
}

export type OidcConfig =
  | null
  | { ok: false; error: string }
  | { ok: true; issuer: string; clientId: string; redirectUri: string; apiBase: string }

export function randomUrlToken(bytes?: number): string
export function codeChallenge(verifier: string): string
export function oidcConfig(env: Record<string, string | undefined>): OidcConfig
export function authorizeRequest(config: Exclude<OidcConfig, null | { ok: false }>, pending: OidcPending): URL
export function tokenEndpoint(config: Exclude<OidcConfig, null | { ok: false }>): string
export function readUnverifiedStringClaim(token: string | undefined, name: string): string
