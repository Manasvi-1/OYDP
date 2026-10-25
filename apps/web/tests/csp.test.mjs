import {test} from 'node:test';
import assert from 'node:assert/strict';
import {contentSecurityPolicy} from '../lib/csp.mjs';
const nonce = 'A'.repeat(43)+'=';
test('production policy requires nonces without inline or eval bypasses',()=>{
  const csp=contentSecurityPolicy(nonce);
  assert.ok(csp.includes(`script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`));
  assert.ok(csp.includes(`style-src 'self' 'nonce-${nonce}'`));
  for(const value of ["'unsafe-inline'", "'unsafe-eval'"]) assert.equal(csp.includes(value),false);
  for(const directive of ["frame-ancestors 'none'","base-uri 'none'","object-src 'none'","form-action 'self'"]) assert.ok(csp.includes(directive));
});
test('development eval is explicit and malformed nonces fail closed',()=>{
  assert.ok(contentSecurityPolicy(nonce,true).includes("'unsafe-eval'"));
  for(const value of ['', 'short', "x'; script-src *", 'A'.repeat(24)+'\n']) assert.throws(()=>contentSecurityPolicy(value));
});
