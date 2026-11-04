import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function keyFrom(secret) {
  if (typeof secret !== 'string' || secret.length < 32 || secret.length > 200) return null
  return createHash('sha256').update(secret, 'utf8').digest()
}

export function seal(payload, secret) {
  const key = keyFrom(secret)
  if (!key) throw new Error('SESSION_SECRET must contain at least 32 characters')
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', key, iv)
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(payload), 'utf8'), cipher.final()])
  return Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString('base64url')
}

export function open(token, secret) {
  const key = keyFrom(secret)
  if (!key || typeof token !== 'string' || token.length < 40 || token.length > 16000) return null
  let raw
  try {
    raw = Buffer.from(token, 'base64url')
  } catch {
    return null
  }
  if (raw.length < 12 + 16 + 2) return null
  try {
    const decipher = createDecipheriv('aes-256-gcm', key, raw.subarray(0, 12))
    decipher.setAuthTag(raw.subarray(12, 28))
    const json = Buffer.concat([decipher.update(raw.subarray(28)), decipher.final()]).toString('utf8')
    const data = JSON.parse(json)
    return data && typeof data === 'object' && !Array.isArray(data) ? data : null
  } catch {
    return null
  }
}

export function asSession(data, now = Date.now()) {
  if (!data || data.v !== 1 || data.kind !== 'session') return null
  if (typeof data.exp !== 'number' || !Number.isFinite(data.exp) || data.exp <= now) return null
  if (typeof data.accessToken !== 'string' || data.accessToken.length < 20 || data.accessToken.length > 12000 || /\s/.test(data.accessToken)) return null
  if (data.tenantId !== null && (typeof data.tenantId !== 'string' || !UUID.test(data.tenantId))) return null
  if (typeof data.sub !== 'string' || data.sub.trim() === '' || data.sub.length > 255) return null
  return {
    v: 1,
    kind: 'session',
    accessToken: data.accessToken,
    tenantId: data.tenantId,
    sub: data.sub,
    exp: data.exp,
  }
}

export function asOidcTransaction(data, now = Date.now()) {
  if (!data || data.v !== 1 || data.kind !== 'oidc') return null
  if (typeof data.exp !== 'number' || !Number.isFinite(data.exp) || data.exp <= now) return null
  for (const field of ['state', 'verifier', 'nonce']) {
    if (typeof data[field] !== 'string' || data[field].length < 16 || data[field].length > 200) return null
  }
  return { v: 1, kind: 'oidc', state: data.state, verifier: data.verifier, nonce: data.nonce, exp: data.exp }
}
