const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const headers = {'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'};
const error = (status, detail) => Response.json({detail}, {status, headers});

// Fixed upstream and an explicit route/method matrix prevent an open proxy.
export async function proxy(request, parts, config = {}) {
  const fetcher = config.fetcher ?? fetch;
  const base = config.base ?? process.env.OYDP_API_ORIGIN;
  const method = request.method;
  const valid = parts[0] === 'v1' && parts[1] === 'properties' && (
    (parts.length === 2 && ['GET','POST'].includes(method)) ||
    (parts.length === 3 && uuid.test(parts[2]) && method === 'GET') ||
    (parts.length === 4 && uuid.test(parts[2]) && (
      (parts[3] === 'claims' && ['GET','POST'].includes(method)) ||
      (parts[3] === 'access' && ['PUT','DELETE'].includes(method)))));
  if (!valid) return error(404, 'Route unavailable');
  const token = request.headers.get('authorization') ?? '';
  const tenant = request.headers.get('x-tenant-id') ?? '';
  if (!/^Bearer [^\s]+$/i.test(token) || token.length > 16384) return error(401, 'Access token required');
  if (!uuid.test(tenant)) return error(422, 'Valid tenant required');
  let origin;
  try {
    origin = new URL(base);
    if (origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/' ||
      !(origin.protocol === 'https:' || (origin.protocol === 'http:' && ['localhost','127.0.0.1'].includes(origin.hostname)))) throw Error();
  } catch { return error(503, 'API connection not configured'); }
  const incoming = new URL(request.url);
  for (const [key, value] of incoming.searchParams) {
    if (method !== 'GET' || !['limit','cursor'].includes(key) || value.length > 512 || incoming.searchParams.getAll(key).length !== 1) return error(422, 'Invalid query');
  }
  let body;
  if (method !== 'GET') {
    if (!(request.headers.get('content-type') ?? '').startsWith('application/json')) return error(415, 'JSON required');
    // Stream limit also covers missing/forged Content-Length.
    const reader = request.body?.getReader();
    let size = 0; const chunks = [];
    if (reader) while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > 65536) { await reader.cancel(); return error(413, 'Request too large'); }
      chunks.push(value);
    }
    body = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    try { JSON.parse(new TextDecoder().decode(body)); } catch { return error(422, 'Invalid JSON'); }
  }
  const url = new URL(parts.join('/'), origin);
  url.search = incoming.search;
  try {
    const upstream = await fetcher(url, {method, headers:{Authorization:token,'X-Tenant-ID':tenant,'Content-Type':'application/json'},
      body, cache:'no-store', redirect:'error', signal:AbortSignal.timeout(10000)});
    // Do not reflect upstream infrastructure errors or authentication cookies.
    if (upstream.status >= 500) return error(503, 'Property service unavailable');
    if (!upstream.headers.get('content-type')?.includes('application/json')) return error(502, 'Invalid service response');
    // Bound decoded response bytes, including chunked responses with no length.
    // A page of 100 maximum-length claims fits within this 8 MiB ceiling.
    const reader = upstream.body?.getReader();
    const chunks = []; let size = 0;
    if (reader) while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > 8 * 1024 * 1024) {
        await reader.cancel(); return error(502, 'Invalid service response');
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    try { JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes)); }
    catch { return error(502, 'Invalid service response'); }
    return new Response(bytes, {status:upstream.status, headers:{...headers,'Content-Type':'application/json'}});
  } catch { return error(503, 'Property service unavailable'); }
}

