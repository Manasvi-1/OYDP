export class ApiError extends Error {
  code: string
  constructor(code: string)
}

export interface PropertyRequest {
  kind: 'list' | 'create' | 'read' | 'claims' | 'claim' | 'identifiers' | 'identifier' | 'evidence' | 'evidence-list' | 'documents' | 'document' | 'audit' | 'requests' | 'request'
  limit?: number
  cursor?: string
  id?: string
  label?: string
  jurisdiction?: string
  statement?: string
  scheme?: string
  identifierValue?: string
  assertionText?: string
  title?: string
  body?: string
  bytes?: Uint8Array
}

export function apiBaseAllowed(value: string): boolean
export function codeForStatus(status: number): string
export function resolvePropertyPath(request: PropertyRequest): { method: string; path: string; body?: Record<string, unknown>; raw?: Uint8Array } | null
export function callPropertyApi(input: {
  base: string
  token: string
  tenantId: string
  request: PropertyRequest
  fetchImpl?: typeof fetch
}): Promise<Record<string, unknown>>
