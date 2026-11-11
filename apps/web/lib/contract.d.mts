export const SESSION_COOKIE: string
export const UUID: RegExp

export interface SessionInput {
  apiBase?: string
  tenantId?: string
  accessToken?: string
}

export interface WorkspaceSession {
  tenantId: string
  accessToken: string
  exp?: number
}

export interface SessionClock {
  key?: string
  now: number
}

export type SessionResult =
  | { ok: true; session: WorkspaceSession }
  | { ok: false; error: string }

export function sessionKeyBytes(key: string | undefined): Buffer | null
export function sealJson(payload: object, key: string | undefined, aad: string): string
export function openJson(value: string | undefined, key: string | undefined, aad: string): Record<string, unknown> | null
export function parseSessionInput(input: SessionInput): SessionResult
export function encodeSession(session: WorkspaceSession, options: SessionClock): string
export function decodeSession(value: string | undefined, options: SessionClock): WorkspaceSession | null
export function messageFromApi(status: number, payload: unknown): string
export function propertiesQuery(cursor?: string): string
export function correctionsQuery(propertyId: string, cursor?: string): string
export function claimsQuery(propertyId: string, cursor?: string): string
export function identifiersQuery(propertyId: string, cursor?: string): string
export function reviewsQuery(propertyId: string, cursor?: string): string
export function documentsQuery(propertyId: string, cursor?: string): string
export function auditQuery(propertyId: string, cursor?: string): string
export function evidenceGraphQuery(propertyId: string): string
export function evidenceConflictsQuery(propertyId: string): string
export function sourcesQuery(cursor?: string): string
export function requestsQuery(propertyId: string, cursor?: string): string
export function notesQuery(propertyId: string, requestId: string, cursor?: string): string
