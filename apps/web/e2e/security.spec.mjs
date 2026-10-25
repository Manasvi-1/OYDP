import {test,expect} from '@playwright/test';

test('fresh server nonces hydrate the workspace and block untrusted inline scripts',async({page,request})=>{
  const forged='A'.repeat(43)+'=';
  const first=await request.get('/',{headers:{'x-nonce':forged,'Content-Security-Policy':"script-src 'unsafe-inline'"}});
  const second=await request.get('/');
  const policy=first.headers()['content-security-policy'];
  const nonce=policy.match(/'nonce-([^']+)'/)[1];
  expect(Buffer.from(nonce,'base64').length).toBe(32);
  expect(nonce).not.toBe(forged);
  expect(policy).not.toContain('unsafe-inline');expect(policy).not.toContain('unsafe-eval');
  expect(second.headers()['content-security-policy']).not.toContain(nonce);
  expect(first.headers()['cache-control']).toContain('no-store');
  const html=await first.text();
  expect(html).toContain(`nonce="${nonce}"`);
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Connect workspace'})).toBeVisible();
  const scripts=await page.locator('script').evaluateAll(nodes=>nodes.map(node=>node.nonce));
  expect(scripts.length).toBeGreaterThan(0);
  expect(scripts.every(Boolean)).toBe(true);
  await page.evaluate(oldNonce=>{
    window.cspViolations=[];
    document.addEventListener('securitypolicyviolation',event=>window.cspViolations.push(event.effectiveDirective));
    for(const nonce of ['',oldNonce]){
      const script=document.createElement('script');if(nonce)script.nonce=nonce;
      script.textContent='window.untrustedScriptRan=true';document.body.appendChild(script);
    }
  },nonce);
  await expect.poll(()=>page.evaluate(()=>window.cspViolations.length)).toBeGreaterThanOrEqual(2);
  expect(await page.evaluate(()=>window.untrustedScriptRan)).toBeUndefined();
});
