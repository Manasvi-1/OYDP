export type OriginResult = { ok: true; origin: string } | { ok: false; error: string }
export type JwksUrlResult = { ok: true; url: string } | { ok: false; error: string }
export type DirectResponse = { ok: true } | { ok: false; error: string }

export function configuredApiBase(env: Record<string, string | undefined>): OriginResult
export function configuredJwksUrl(env: Record<string, string | undefined>): JwksUrlResult
export function propertyRequestUrl(origin: string, path: string): URL | null
export function directPropertyResponse(status: number): DirectResponse
