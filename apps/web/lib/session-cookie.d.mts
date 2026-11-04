export interface SealedSession {
  v: 1
  kind: 'session'
  accessToken: string
  tenantId: string | null
  sub: string
  exp: number
}

export interface OidcTransaction {
  v: 1
  kind: 'oidc'
  state: string
  verifier: string
  nonce: string
  exp: number
}

export function seal(payload: SealedSession | OidcTransaction, secret: string): string
export function open(token: string | undefined, secret: string): Record<string, unknown> | null
export function asSession(data: unknown, now?: number): SealedSession | null
export function asOidcTransaction(data: unknown, now?: number): OidcTransaction | null
