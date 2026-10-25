'use client';
import {useRef, useState} from 'react';

export default function Workspace() {
  const credentials = useRef(null);
  const generation = useRef(0);
  const [connected,setConnected] = useState(false);
  const [properties,setProperties] = useState([]);
  const [next,setNext] = useState(null);
  const [selected,setSelected] = useState(null);
  const [claims,setClaims] = useState([]);
  const [claimNext,setClaimNext] = useState(null);
  const [message,setMessage] = useState('');
  const [busy,setBusy] = useState(false);
  function clear() {
    generation.current++; credentials.current=null; setConnected(false);
    setProperties([]);setNext(null);setSelected(null);setClaims([]);setClaimNext(null);
  }
  async function api(path, method='GET', body) {
    const c=credentials.current;
    if (!c) throw Error('Connect your session first.');
    const response=await fetch('/api/v1/properties'+path,{method,cache:'no-store',headers:{Authorization:'Bearer '+c.token,'X-Tenant-ID':c.tenant,'Content-Type':'application/json'},body:body ? JSON.stringify(body):undefined});
    if (response.status===401) {clear();throw Error('Session expired or invalid. Connect again.');}
    if (!response.ok) throw Error(({403:'Permission or MFA required.',404:'Property or recipient unavailable.',422:'Check your input.',503:'Property service unavailable.'})[response.status] ?? 'Request failed.');
    return response.json();
  }
  async function run(action) {
    if (busy) return;
    setBusy(true);setMessage('');const version=generation.current;
    try {await action(()=>version===generation.current);} catch(e) {setMessage(e.message);} finally {setBusy(false);}
  }
  async function load(cursor, current) {
    const page=await api(cursor?'?cursor='+encodeURIComponent(cursor):'');
    if(current()){setProperties(page.items);setNext(page.next_cursor);}
  }
  function connect(event) {
    event.preventDefault();const form=event.currentTarget;const data=new FormData(form);
    clear();credentials.current={tenant:data.get('tenant').trim(),token:data.get('token').trim()};
    form.reset();setConnected(true);run(current=>load(null,current));
  }
  async function open(property,current) {
    setSelected(null);setClaims([]);setClaimNext(null);
    const record=await api('/'+property.id);
    const history=await api('/'+property.id+'/claims');
    if(current()){setSelected(record);setClaims(history.items);setClaimNext(history.next_cursor);}
  }
  const submit=(action)=>event=>{event.preventDefault();const form=event.currentTarget;const data=Object.fromEntries(new FormData(form));run(async current=>{await action(data,current);if(current())form.reset();});};
  return <main>
    <header><span className="brand">OYDP</span><span>OWN YOUR DREAM PROPERTY</span><span className="tag">Private workspace · Pre-alpha</span></header>
    <section className="intro"><p className="eyebrow">PROPERTY IDENTITY</p><h1>Keep the property story<br/>grounded in evidence.</h1><p>Create private candidates, record attributed claims and control read access.</p></section>
    <aside className="notice">Candidate records and user claims are unverified. Jurisdiction is user-entered and unresolved. This workspace does not establish legal title or official approval.</aside>
    {!connected ? <section className="panel"><h2>Connect an API session</h2><p>Operator preview: use an existing OIDC API access token. Browser sign-in is pending. Tokens stay in memory and clear on disconnect or reload.</p><form onSubmit={connect}><label>Tenant ID<input name="tenant" required pattern="[0-9a-fA-F-]{36}" autoComplete="off"/></label><label>API access token<input name="token" type="password" required autoComplete="off" spellCheck="false"/></label><button disabled={busy}>Connect workspace</button></form></section> : <>
      <div className="toolbar"><h2>Your property candidates</h2><button disabled={busy} onClick={()=>run(c=>load(null,c))}>Refresh</button><button disabled={busy} onClick={()=>{clear();setMessage('Session cleared.');}}>Disconnect</button></div>
      <div className="columns"><section className="panel"><h3>Create a candidate</h3><form onSubmit={submit(async(data,current)=>{await api('','POST',data);if(current())await load(null,current);})}><label>Property label<input name="label" maxLength={200} required/></label><label>Jurisdiction · user-entered<input name="jurisdiction" maxLength={100} required/></label><button disabled={busy}>Create private candidate</button></form><h3>Accessible candidates</h3>{!properties.length && <p>No accessible candidates on this page.</p>}<ul>{properties.map(p=><li key={p.id}><button className="property" disabled={busy} onClick={()=>run(c=>open(p,c))}>{p.label}<small>{p.jurisdiction} · Unverified</small></button></li>)}</ul>{next&&<button disabled={busy} onClick={()=>run(c=>load(next,c))}>Next candidates</button>}</section>
      <section className="panel">{selected ? <><p className="eyebrow">PRIVATE CANDIDATE</p><h2>{selected.label}</h2><p>{selected.jurisdiction}</p><small>Record ID: {selected.id}</small><h3>Claim history</h3>{!claims.length&&<p>No claims recorded on this page.</p>}<ol>{claims.map(c=><li key={c.id}><span className="tag">User claim · Unverified</span><p className="statement">{c.statement}</p><small>Recorded by {c.created_by} · {new Date(c.recorded_at).toLocaleString()}</small></li>)}</ol>{claimNext&&<button disabled={busy} onClick={()=>run(async current=>{const page=await api('/'+selected.id+'/claims?cursor='+encodeURIComponent(claimNext));if(current()){setClaims(page.items);setClaimNext(page.next_cursor);}})}>Next claims</button>}<h3>Record a claim</h3><p>Creator write permission and MFA are required. Claims are append-only.</p><form onSubmit={submit(async(data,current)=>{await api('/'+selected.id+'/claims','POST',data);if(current())await open(selected,current);})}><label>Statement<textarea name="statement" maxLength={10000} required/></label><button disabled={busy}>Record unverified claim</button></form><h3>Read access</h3><p>Creator permission and MFA are required. Recipients must already belong to this tenant.</p><form onSubmit={submit(async(data)=>{await api('/'+selected.id+'/access','PUT',{recipient_subject:data.recipient_subject,expires_at:new Date(data.expires_at).toISOString()});setMessage('Read access saved.');})}><label>Recipient subject<input name="recipient_subject" maxLength={255} required/></label><label>Expiry · your local time, within 30 days<input name="expires_at" type="datetime-local" required/></label><button disabled={busy}>Grant read access</button></form><form onSubmit={submit(async(data)=>{await api('/'+selected.id+'/access','DELETE',data);setMessage('Read access revoked.');})}><label>Recipient subject to revoke<input name="recipient_subject" maxLength={255} required/></label><button disabled={busy}>Revoke read access</button></form></> : <><h2>Select a candidate</h2><p>Open an accessible record to read its claim history and manage permitted actions.</p></>}</section></div>
    </>}
    <p role="status" aria-live="polite">{busy?'Working…':message}</p><footer>OYDP · Evidence before conclusions</footer>
  </main>;
}
