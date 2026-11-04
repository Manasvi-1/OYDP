export class ApiError extends Error {
  code: string
  constructor(code: string)
}

export interface PropertyRequest {
  kind: 'list' | 'create' | 'read' | 'claims' | 'claim'
  limit?: number
  cursor?: string
  id?: string
  label?: string
  jurisdiction?: string
  statement?: string
}

export function apiBaseAllowed(value: string): boolean
export function codeForStatus(status: number): string
export function resolvePropertyPath(request: PropertyRequest): { method: string; path: string; body?: { label: string; jurisdiction: string } | { statement: string } } | null
export function callPropertyApi(input: {
  base: string
  token: string
  tenantId: string
  request: PropertyRequest
  fetchImpl?: typeof fetch
}): Promise<Record<string, unknown>>
