export const SESSION_COOKIE: string
export const UUID: RegExp

export interface SessionInput {
  apiBase?: string
  tenantId?: string
  accessToken?: string
}

export interface WorkspaceSession {
  apiBase: string
  tenantId: string
  accessToken: string
}

export type SessionResult =
  | { ok: true; session: WorkspaceSession }
  | { ok: false; error: string }

export function parseSessionInput(input: SessionInput): SessionResult
export function encodeSession(session: WorkspaceSession): string
export function decodeSession(value: string | undefined): WorkspaceSession | null
export function messageFromApi(status: number, payload: unknown): string
export function propertiesQuery(cursor?: string): string
export function correctionsQuery(propertyId: string, cursor?: string): string
export function claimsQuery(propertyId: string, cursor?: string): string
