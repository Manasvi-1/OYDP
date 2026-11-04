import {test} from 'node:test';
import assert from 'node:assert/strict';
import {proxy} from '../lib/proxy.mjs';
const tenant='11111111-1111-1111-1111-111111111111';
const id='22222222-2222-2222-2222-222222222222';
const options={base:'http://127.0.0.1:8000',fetcher:async()=>Response.json({items:[],next_cursor:null})};
function request(path='',method='GET',body,extra={}) {return new Request('http://localhost/api/v1/properties'+path,{method,headers:{Authorization:'Bearer test-token','X-Tenant-ID':tenant,'Content-Type':'application/json',...extra},body:body===undefined?undefined:JSON.stringify(body)});}
test('forwards only explicit bearer/tenant headers to fixed upstream without cache or redirect',async()=>{
 let captured;
 const response=await proxy(request('?limit=25'),['v1','properties'],{...options,fetcher:async(url,init)=>{captured={url,init};return Response.json({items:[],next_cursor:null});}});
 assert.equal(response.status,200);assert.equal(captured.url.href,'http://127.0.0.1:8000/v1/properties?limit=25');
 assert.deepEqual(captured.init.headers,{Authorization:'Bearer test-token','X-Tenant-ID':tenant,'Content-Type':'application/json'});
 assert.equal(captured.init.redirect,'error');assert.equal(captured.init.cache,'no-store');assert.equal(response.headers.get('cache-control'),'no-store');
});
test('missing token, invalid tenant, unavailable origin fail closed before upstream',async()=>{
 let calls=0;const config={...options,fetcher:async()=>{calls++;throw Error();}};
 assert.equal((await proxy(request('', 'GET',undefined,{Authorization:''}),['v1','properties'],config)).status,401);
 assert.equal((await proxy(request('', 'GET',undefined,{'X-Tenant-ID':'bad'}),['v1','properties'],config)).status,422);
 assert.equal((await proxy(request(),['v1','properties'],{...config,base:'https://evil.invalid/path'})).status,503);
 assert.equal(calls,0);
});
test('rejects arbitrary paths, traversal, unsupported methods and duplicate queries',async()=>{
 for(const path of [['v1','properties','..'],['healthz'],['v1','properties',id,'other']]) assert.equal((await proxy(request(),path,options)).status,404);
 assert.equal((await proxy(request('','DELETE',{}),['v1','properties'],options)).status,404);
 assert.equal((await proxy(request('?limit=1&limit=2'),['v1','properties'],options)).status,422);
 assert.equal((await proxy(request('?token=secret'),['v1','properties'],options)).status,422);
});
test('preserves authorization denials and sanitizes infrastructure failures',async()=>{
 const denied=await proxy(request(),['v1','properties'],{...options,fetcher:async()=>Response.json({detail:'Tenant membership required'},{status:403})});assert.equal(denied.status,403);
 const failed=await proxy(request(),['v1','properties'],{...options,fetcher:async()=>new Response('database password secret',{status:500})});
 assert.equal(failed.status,503);assert.equal((await failed.text()).includes('secret'),false);
});
test('forwards claim bodies and enforces streaming size limit',async()=>{
 let payload;
 const response=await proxy(request('/'+id+'/claims','POST',{statement:'Unverified'}),['v1','properties',id,'claims'],{...options,fetcher:async(url,init)=>{payload=JSON.parse(new TextDecoder().decode(init.body));return Response.json({id},{status:201});}});
 assert.equal(response.status,201);assert.deepEqual(payload,{statement:'Unverified'});
 assert.equal((await proxy(request('','POST',{label:'x'.repeat(65536)}),['v1','properties'],options)).status,413);
});
test('does not forward upstream cookies',async()=>{
 const response=await proxy(request(),['v1','properties'],{...options,fetcher:async()=>Response.json({}, {headers:{'Set-Cookie':'secret=value'}})});
 assert.equal(response.headers.get('set-cookie'),null);
});


test('rejects malformed JSON and invalid UTF-8 from upstream without reflecting content',async()=>{
 for (const body of ['{secret infrastructure text', new Uint8Array([0xff])]) {
   const response=await proxy(request(),['v1','properties'],{...options,fetcher:async()=>new Response(body,{headers:{'Content-Type':'application/json'}})});
   assert.equal(response.status,502);
   assert.deepEqual(await response.json(),{detail:'Invalid service response'});
 }
});
test('bounds chunked upstream responses and cancels oversized streams',async()=>{
 let cancelled=false;
 const stream=new ReadableStream({pull(controller){controller.enqueue(new Uint8Array(1024*1024));},cancel(){cancelled=true;}});
 const response=await proxy(request(),['v1','properties'],{...options,fetcher:async()=>new Response(stream,{headers:{'Content-Type':'application/json'}})});
 assert.equal(response.status,502);assert.equal(cancelled,true);
 assert.deepEqual(await response.json(),{detail:'Invalid service response'});
});
