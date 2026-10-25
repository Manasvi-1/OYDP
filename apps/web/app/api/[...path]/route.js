import { proxy } from '../../../lib/proxy.mjs';
export const dynamic = 'force-dynamic';
async function handle(request, context) {
  const {path} = await context.params;
  return proxy(request, path);
}
export {handle as GET, handle as POST, handle as PUT, handle as DELETE};
