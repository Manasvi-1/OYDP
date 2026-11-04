const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1'])

function fail(error) {
  return { ok: false, error }
}

function parsedOrigin(raw, label) {
  const value = String(raw ?? '').trim()
  if (!value) return fail(`${label} is not configured`)
  let url
  try {
    url = new URL(value)
  } catch {
    return fail(`${label} is invalid`)
  }
  if (url.username || url.password) return fail(`${label} cannot include credentials`)
  if (url.search) return fail(`${label} cannot include a query`)
  if (url.hash) return fail(`${label} cannot include a fragment`)
  const local = url.protocol === 'http:' && LOCAL_HOSTS.has(url.hostname)
  if (url.protocol !== 'https:' && !local) return fail(`${label} must be https, or http on localhost`)
  return { ok: true, url }
}

export function configuredApiBase(env) {
  const parsed = parsedOrigin(env?.PROPERTY_API_BASE, 'Property API origin')
  if (!parsed.ok) return parsed
  if (parsed.url.pathname !== '/' && parsed.url.pathname !== '') {
    return fail('Property API origin cannot include a path')
  }
  return { ok: true, origin: parsed.url.origin }
}

export function configuredJwksUrl(env) {
  const parsed = parsedOrigin(env?.OIDC_JWKS_URL, 'Identity provider key URL')
  if (!parsed.ok) return parsed
  return { ok: true, url: parsed.url.origin + parsed.url.pathname }
}

export function propertyRequestUrl(origin, path) {
  if (typeof origin !== 'string' || typeof path !== 'string') return null
  if (!path.startsWith('/v1/') || path.includes('://') || path.includes('\\') || /[\u0000-\u0020]/.test(path)) return null
  let target
  try {
    target = new URL(path, origin)
  } catch {
    return null
  }
  if (target.origin !== origin || target.username || target.password || target.hash) return null
  if (!target.pathname.startsWith('/v1/')) return null
  return target
}

export function directPropertyResponse(status) {
  if (status >= 300 && status < 400) {
    return { ok: false, error: 'Property service refused to answer directly' }
  }
  return { ok: true }
}
