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
  await expect(page.getByRole('button',{name:'Continue'})).toBeVisible();
  const scripts=await page.locator('script').evaluateAll(nodes=>nodes.map(node=>node.nonce));
  expect(scripts.length).toBeGreaterThan(0);
  expect(scripts.every(Boolean)).toBe(true);
  // Inject parser-created markup into a real response. Debugger/evaluate-created
  // scripts are not a faithful simulation of untrusted HTML under strict-dynamic.
  await page.addInitScript(()=>{
    window.cspViolations=[];
    document.addEventListener('securitypolicyviolation',event=>window.cspViolations.push(event.effectiveDirective));
  });
  await page.route('**/*',async route=>{
    if(!route.request().isNavigationRequest()){await route.continue();return;}
    const response=await route.fetch();
    const html=await response.text();
    const attack=`<script>window.untrustedScriptRan=true</script><script nonce="${nonce}">window.replayedNonceRan=true</script>`;
    await route.fulfill({response,body:html.replace('</head>',attack+'</head>')});
  });
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Continue'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>window.cspViolations.length)).toBeGreaterThanOrEqual(2);
  expect(await page.evaluate(()=>window.untrustedScriptRan)).toBeUndefined();
  expect(await page.evaluate(()=>window.replayedNonceRan)).toBeUndefined();
});
