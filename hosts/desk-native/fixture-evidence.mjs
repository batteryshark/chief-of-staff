// Pure consistency validator, NOT native-origin authentication. Missing host
// callback/readback data stays unknown; never synthesize it from summaries.
const canonical=v=>JSON.stringify(v,(_,x)=>x && typeof x==='object' && !Array.isArray(x)
  ? Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])) : x);
const eq=(a,b)=>canonical(a)===canonical(b);
export function validateSmoke(binding,logs) {
  try {return correlate(binding,logs);} catch(error) {return {state:'unknown-STOP',reason:error.message,approval:false};}
}
function correlate(b,logs) {
  const need=(ok,why)=>{if(!ok) throw Error(why);};
  need(b?.phase==='operator-bound-not-native-verified' && logs.length===2,'binding/log scope');
  const events=logs.flatMap(l=>l.events);
  need(events.every(e=>['native','bridge','managed','registered-tool','native-caller','catalog','executor-denial'].includes(e.kind)),'unknown event kind');
  need(events.length>0 && events.length<=128 && events.every(e=>Number.isFinite(e.at) && e.kind!=='unknown'),'event cap/interleaving');
  need(Math.max(...events.map(e=>e.at))-Math.min(...events.map(e=>e.at))<=120000,'run clock');
  for(const l of logs) need(l.events.every((e,i)=>e.seq===i+1 && (!i || e.at>=l.events[i-1].at)),'sequence/clock');
  const rows=(kind,op)=>events.filter(e=>e.kind===kind && e.data.op===op);
  const one=(kind,op,predicate=()=>true)=>{const r=rows(kind,op).filter(e=>predicate(e.data));need(r.length===1,'missing/duplicate '+kind+':'+op);return r[0];};
  const before=(a,z)=>{const l=logs.find(l=>l.events.includes(a));need(l?.events.includes(z) && l.events.indexOf(a)<l.events.indexOf(z),'operation order');};
  const lead=b.sessions.find(s=>s.agent==='proof-lead-a'),desk=b.sessions.find(s=>s.agent==='proof-desk');
  const report=one('registered-tool','desk_report'),inbox=one('registered-tool','desk_inbox');
  need(events.filter(e=>e.kind==='registered-tool').length===2,'unexpected typed action');
  const call=report.data.input.call,dc=inbox.data.input.call;
  need(call.sessionID===lead.id && call.agent===lead.agent && dc.sessionID===desk.id && dc.agent===desk.agent,'tool identity');
  need(eq(report.data.input.args,{report:b.report}),'exact fixed report');
  const prep=one('bridge','prepare_input'),p=prep.data.value;
  const {send:preparedSend,...planned}=p;
  need(eq(prep.data.input.report,b.report) && eq(p.report,b.report) && eq(prep.data.input.call,call) && eq(p.call,call),'prepared report/call');
  need(p.id && p.send===true && p.state==='planned' && p.auth.sender===lead.id && p.auth.target===desk.id
    && p.auth.project==='lead-a' && p.auth.path===lead.location.directory && p.auth.epoch===1,'prepared identity/epoch');
  need(eq(JSON.parse(p.body),{inputId:p.id,desk_report:b.report}) && report.data.value.inputId===p.id
    && eq(inbox.data.input.args,{inputId:p.id}) && inbox.data.value.filed===true,'input/report result');
  const claim=one('bridge','claim_input'),prompt=one('native','prompt'),admit=one('bridge','admit_input');
  before(prep,claim);before(claim,prompt);before(prompt,admit);before(admit,report);
  need(claim.data.input.input_id===p.id && claim.data.value.id===p.id && claim.data.value.state==='uncertain' && claim.data.value.send===true,'input claim');
  need(eq(claim.data.value,{...p,state:'uncertain'}),'claimed persisted input conflict');
  need(eq(prompt.data.input,{sessionID:desk.id,id:p.id,text:p.body,metadata:{deskInput:p.id},delivery:'queue',resume:true}),'native prompt target/input');
  const admission=(v,id,type,target,text)=>v?.id===id && v.type===type && v.sessionID===target && v.payload?.text===text;
  need(admission(prompt.data.value,p.id,'user',desk.id,p.body) && eq(admit.data.input,{input_id:p.id,admission:prompt.data.value})
    && admit.data.value.state==='admitted' && eq(admit.data.value.admission,prompt.data.value),'native prompt admission');
  need(eq(admit.data.value,{...planned,state:'admitted',admission:prompt.data.value}),'admitted input ledger conflict');
  const read=one('bridge','input'),file=one('bridge','file_input'),seq=inbox.data.value.receiptId;
  before(read,file);before(file,inbox);
  need(read.data.input.input_id===p.id && eq(read.data.value,admit.data.value) && file.data.input.input_id===p.id
    && eq(file.data.input.record,{id:p.id,type:'user',text:p.body}) && file.data.value.seq===seq
    && file.data.value.verified===true && file.data.value.action==='ack','durable filing');
  need(admit.at<=read.at,'admission before desk read');
  const actions=file.data.value.actions;
  need(actions.length===3 && new Set(actions.map(a=>a.kind)).size===3
    && actions.every(a=>['receipt','status-note','overview-note'].includes(a.kind) && a.id===seq+':'+a.kind
      && a.receipt===seq && a.state==='planned' && eq(a.auth,p.auth))
    && new Set(actions.map(a=>a.native_id)).size===3,'unique exact action set');
  const receipt=actions.find(a=>a.kind==='receipt'),send=one('native','synthetic'),ac=one('bridge','claim_action'),aa=one('bridge','action_admitted');
  need(receipt.target===lead.id && receipt.body===`Desk receipt ${seq}: filed. No approval implied. Project/overview projection pending. Source input ${p.id}.`,'receipt content/recipient');
  before(ac,send);before(send,aa);
  need(ac.data.input.action_id===receipt.id && ac.data.value.state==='uncertain' && ac.data.value.send===true
    && eq(send.data.input,{sessionID:lead.id,id:receipt.native_id,text:receipt.body,delivery:'queue',resume:true,metadata:{deskAction:receipt.id}})
    && admission(send.data.value,receipt.native_id,'synthetic',lead.id,receipt.body)
    && eq(aa.data.input,{action_id:receipt.id,evidence:send.data.value}) && aa.data.value.state==='completed'
    && aa.data.value.id===receipt.id && eq(aa.data.value.evidence,send.data.value),'receipt admission');
  need(eq(ac.data.value,{...receipt,state:'uncertain',send:true})
    && eq(aa.data.value,{...receipt,state:'completed',evidence:send.data.value}),'receipt action identity/result');
  // Native snapshots must agree with the actual registered invocation AND result.
  const contexts=rows('native','context');
  need(events.filter(e=>e.kind==='native-caller').length===2 && events.filter(e=>e.kind==='catalog').length===2
    && events.filter(e=>e.kind==='executor-denial').length===6,'extra caller/catalog/denial identity');
  for(const [s,r,name] of [[lead,report,'desk_report'],[desk,inbox,'desk_inbox']]) {
    const c=r.data.input.call;let found=false;
    need(c.messageID && c.id,'message/call IDs');
    for(const e of contexts.filter(e=>e.data.input.sessionID===s.id)) {
      need(Array.isArray(e.data.value),'context shape');
      const messages=e.data.value.filter(m=>m.id===c.messageID);need(messages.length<=1,'duplicate native message');
      for(const m of messages) need(m.content?.filter(p=>p.type==='tool').length===1,'duplicate/missing native tool part');
      for(const m of e.data.value) for(const part of m.content||[]) if(part.type==='tool') {
        need(m.id===c.messageID && m.type==='assistant' && part.id===c.id && part.name===name,'interleaved tool identity');
        need(part.state?.status==='completed' && eq(part.state.input,r.data.input.args)
          && part.state.output===JSON.stringify(r.data.value),'native completed input/output conflict');found=true;
      }
    }
    need(found,'completed native tool missing/compacted');
    const verified=events.filter(e=>e.kind==='native-caller' && e.data.call.sessionID===s.id);
    need(verified.length===1 && eq(verified[0].data.call,c) && verified[0].data.native.id===s.id
      && verified[0].data.native.agent===s.agent && verified[0].data.native.projectID===s.projectID
      && eq(verified[0].data.native.location,s.location),'native caller identity');
    const first=s===lead?prep:file;
    before(verified[0],first);
    for(const id of ['read','write','openchamber_knowledge']) {
      const pin=b.metadataPins.flatMap(m=>m.tools).find(t=>t.id===id)?.descriptor_sha256;
      const denials=events.filter(e=>e.kind==='executor-denial' && eq(e.data.call,c) && e.data.id===id);
      need(denials.length===1 && denials[0].data.denied===true && denials[0].data.descriptor_sha256===pin,'pinned executor denial');
      before(verified[0],denials[0]);before(denials[0],first);
    }
    need(events.filter(e=>e.kind==='catalog' && e.data.agent===s.agent).length===1,'catalog missing/duplicate');
  }
  const nativeIdentity=(v,s)=>v?.id===s?.id && v.agent===s.agent && v.projectID===s.projectID
    && eq(v.location,s.location) && v.model?.providerID+'/'+v.model?.id===s.model && !v.time?.archived;
  for(const e of rows('native','get')) need(nativeIdentity(e.data.value,b.sessions.find(s=>s.id===e.data.input.sessionID)),'current native identity/model');
  for(const s of [lead,desk]) need(rows('native','get').some(e=>e.data.input.sessionID===s.id),'native get missing');
  for(const e of events.filter(e=>e.kind==='bridge')) for(const k of ['sender','desk','chief']) if(e.data.input[k]) {
    const s=b.sessions.find(s=>s.id===(k==='sender'?lead.id:k==='desk'?desk.id:b.sessions.find(s=>s.agent==='proof-chief').id));
    need(nativeIdentity(e.data.input[k],s),'bridge native identity');
  }
  for(const e of contexts) need([lead.id,desk.id].includes(e.data.input.sessionID),'foreign context');
  const active=(sid,id,type,text)=>contexts.some(e=>e.data.input.sessionID===sid && e.data.value.filter(m=>m.id===id).length===1
    && e.data.value.some(m=>m.id===id && m.type===type && m.text===text));
  for(const [sid,id,type,text] of [[desk.id,p.id,'user',p.body],[lead.id,receipt.native_id,'synthetic',receipt.body]])
    for(const e of contexts.filter(e=>e.data.input.sessionID===sid)) {
      const hits=e.data.value.filter(m=>m.id===id);
      need(hits.length<=1 && hits.every(m=>m.type===type && m.text===text),'conflicting/duplicate active readback');
    }
  need(active(desk.id,p.id,'user',p.body) && active(lead.id,receipt.native_id,'synthetic',receipt.body),'active input/receipt readback');
  const ledger=one('bridge','smoke_state'),state=ledger.data.value;
  before(file,ledger);before(ledger,inbox);
  need(ledger.data.input.input_id===p.id && state.input.id===p.id && state.input.state==='filed' && state.input.receipt===seq
    && eq(state.input.report,b.report) && eq(state.input.auth,p.auth) && eq(state.input.admission,prompt.data.value)
    && eq(state.input.readback,file.data.input.record) && eq(state.input.call,call),'durable input ledger');
  need(eq(state.counts,{native_inputs:1,native_actions:3,native_notes:2,events:1}) && state.event.seq===seq
    && state.event.verified===1 && state.event.sender===lead.id && eq(state.event.payload,b.report)
    && state.watermark===1 && state.snapshot.watermark===state.watermark
    && state.snapshot.projects['lead-a'].seq===seq && state.snapshot.projects['lead-a'].source_revision===b.report.source_revision,'durable source/watermark');
  need(Object.entries(b.report).every(([k,v])=>eq(state.snapshot.projects['lead-a'][k],v))
    && Object.keys(state.snapshot.projects).join()==='lead-a' && eq(state.snapshot.missing,['lead-b']) && state.snapshot.quarantined===0,'source snapshot report');
  need(state.actions.length===3 && new Set(state.actions.map(a=>a.id)).size===3,'durable action set');
  need(eq(state.actions.find(a=>a.id===receipt.id),aa.data.value),'durable receipt ledger');
  need(Object.keys(state.notes).sort().join()==='@overview,lead-a','durable Note scope set');
  need(rows('managed','knowledge.save').length===2 && rows('managed','knowledge.list').length===4,'managed operation set');
  for(const a of actions.filter(a=>a.kind.endsWith('-note'))) {
    const select=d=>d.input.action_id===a.id;
    const prepare=one('bridge','note_prepare',select),returned=one('bridge','note_returned',select),reconcile=one('bridge','note_reconcile',select),n=prepare.data.value;
    const inspect=one('bridge','inspect_action',select);before(inspect,prepare);need(eq(inspect.data.value,a),'inspected Note action');
    before(prepare,returned);before(returned,reconcile);before(reconcile,ledger);
    const scope=a.kind==='overview-note'?'@overview':'lead-a',directory=scope==='@overview'?desk.location.directory:lead.location.directory;
    const projectId=b.knowledge.find(k=>k.directory===directory)?.projectId;
    need(n.send===true && n.state==='uncertain' && n.note_id===null && n.action===a.id && n.scope===scope
      && n.directory===directory && n.projectId===projectId && n.creator===desk.id && /^[a-f0-9]{32}$/.test(n.nonce)
      && n.proposed.endsWith('\nNative intent: '+n.nonce) && n.watermark===state.watermark,'Note intent/source');
    const saved=returned.data.input.saved,note=saved.note,id=note?.id;
    need(id && saved.projectId===projectId && note.body===n.proposed && note.origin?.sessionId===desk.id
      && !n.before_ids.includes(id) && returned.data.value.note_id===id && eq(returned.data.value.returned,saved),'actual saved Note/returned ID');
    const {send:noteSend,...intent}=n;
    need(eq(returned.data.value,{...intent,note_id:id,returned:saved}),'returned durable intent conflict');
    const v=reconcile.data.value,list=reconcile.data.input.listing;
    need(list.projectId===projectId && Array.isArray(list.notes) && list.notes.filter(x=>x.id===id).length===1
      && eq(list.notes.find(x=>x.id===id),note) && v.state==='applied' && v.note_id===id && v.pending_latest===false
      && v.watermark===n.watermark && v.body===n.proposed && eq(v.readback,note) && eq(v.returned,saved)
      && v.nonce===n.nonce && v.proposed===n.proposed,'exact Note readback/watermark');
    need(eq(v,{...returned.data.value,state:'applied',note_id:id,body:n.proposed,readback:note,pending_latest:false}),'reconciled durable intent conflict');
    const save=one('managed','knowledge.save',d=>d.input.parameters.directory===directory);
    need(eq(save.data.input,{call:dc,parameters:{directory,kind:'note',body:n.proposed}}) && eq(save.data.value,saved),'actual managed save input/result');
    before(prepare,save);before(save,returned);
    const lists=rows('managed','knowledge.list').filter(e=>e.data.input.parameters.directory===directory);
    need(lists.length===2 && lists.every(e=>eq(e.data.input,{call:dc,parameters:{directory}})),'managed list identity/scope');
    before(lists[0],prepare);before(returned,lists[1]);before(lists[1],reconcile);
    need(eq(lists[0].data.value,prepare.data.input.listing) && eq(lists[1].data.value,list)
      && eq(n.before_ids,lists[0].data.value.notes.map(x=>x.id)),'actual list data');
    need(eq(state.notes[scope],v),'durable Note ledger');
    const durable=state.actions.find(x=>x.id===a.id);
    need(durable?.state==='completed' && durable.note_id===id && durable.watermark===state.watermark
      && durable.pending_latest===false && eq(durable.auth,a.auth),'durable Note action');
  }
  const counts={prepare_input:1,claim_input:1,admit_input:1,input:1,file_input:1,claim_action:1,action_admitted:1,
    inspect_action:2,check_send:3,note_prepare:2,note_returned:2,note_reconcile:2,smoke_state:1};
  for(const [op,count] of Object.entries(counts)) need(rows('bridge',op).length===count,'bridge operation set '+op);
  need(events.filter(e=>e.kind==='bridge').every(e=>Object.hasOwn(counts,e.data.op)),'unexpected bridge operation');
  need(events.filter(e=>e.kind==='native').every(e=>['get','context','prompt','synthetic'].includes(e.data.op)),'unexpected native operation');
  need(events.filter(e=>e.kind==='managed').length===6,'unexpected managed operation');
  for(const a of actions) {
    const checked=one('bridge','check_send',d=>d.input.action_id===a.id);need(checked.data.value.current===true,'fresh action authorization');
    if(a.kind==='receipt') {before(ac,checked);before(checked,send);} else {
      before(one('bridge','note_prepare',d=>d.input.action_id===a.id),checked);
      before(checked,one('bridge','note_returned',d=>d.input.action_id===a.id));
    }
  }
  return {state:'correlated-first-smoke-only',receiptId:seq,inputId:p.id,actionIDs:actions.map(a=>a.id),approval:false,
    limits:'Consistency only; trusted actual native callback provenance and settled final cleanup still required. Not JSON authentication, UI/day-use or whole-matrix proof.'};
}
