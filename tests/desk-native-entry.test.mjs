// Source-only tests. Nothing here is a real native call or integration proof.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import entry,{preflight} from '../hosts/desk-native/fixture-entry.mjs';
import {pendingConfig} from '../hosts/desk-native/fixture-config.mjs';
import {pathToFileURL} from 'node:url';
import {fixtureAssets} from '../hosts/desk-native/fixture-assets.mjs';
import {stage,collect,benignReport,canonical,validateAck,strictJSON} from '../hosts/desk-native/fixture-operator.mjs';
import {observer} from '../hosts/desk-native/fixture-observer.mjs';
import {validateSmoke} from '../hosts/desk-native/fixture-evidence.mjs';

const source=new URL('../',import.meta.url);
const sha=x=>createHash('sha256').update(x).digest('hex');
function operatorFixture(t) {
  const parent=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'operator-FAKE-')));t.after(()=>fs.rmSync(parent,{recursive:true,force:true}));
  const root=path.join(parent,'F');fs.mkdirSync(root,{mode:0o700});
  const generated=path.join(parent,'agent-tool/openchamber-agent-tool/index.js');fs.mkdirSync(path.dirname(generated),{recursive:true,mode:0o700});fs.writeFileSync(generated,'// OFFLINE FAKE generated executor source\n',{mode:0o600});
  stage(root,'/usr/bin/python3',generated);
  const write=(rel,v)=>fs.writeFileSync(path.join(root,rel),JSON.stringify(v),{mode:0o600});
  const config=pendingConfig(root,'/usr/bin/python3');config.plugins[0].options.enabled=true;write('.opencode/opencode.json',config); // OFFLINE only, no native load
  const input={quiescent:true,expectedEpoch:1,origin:'trusted-operator-saved-managed-responses',model:'openai/offline-fake',observed:new Date().toISOString(),sessions:[],knowledge:[]};
  for(const [agent,dir] of [['proof-desk','home'],['proof-chief','home'],['proof-lead-a','lead-a'],['proof-lead-b','lead-b']]) input.sessions.push({id:'ses_'+agent.replaceAll('-',''),agent,projectID:'global',location:{directory:path.join(root,dir)},time:{},model:input.model,status:'idle',disabled:false,goalActive:false});
  for(const dir of ['home','lead-a','lead-b']) input.knowledge.push({directory:path.join(root,dir),projectId:'managed-'+dir,disabled:false});
  for(const [i,o] of [...input.sessions,...input.knowledge].entries()) {
    const rel='evidence/response-'+i+'.json',action=o.id?'session.list':'knowledge.list';
    write(rel,{OFFLINE_FAKE:true,request:{action,parameters:{directory:o.location?.directory||o.directory,...(o.id?{withStatus:true}:{})}},
      response:{schemaVersion:1,ok:true,action,data:o.id?{sessions:[{...o,model:{providerID:'openai',id:'offline-fake'},status:{type:'idle'}}]}:{projectId:o.projectId,notes:[],todos:[],plans:[]}}});
    o.response_file=path.join(root,rel);o.response_sha256=sha(fs.readFileSync(o.response_file));
  }
  const report=benignReport(input.observed);
  input.rule={id:'fixture-first-smoke',project:'lead-a',action:'ack',active:true,fixture_only:true,report_hash:sha(canonical(report)),recipient:input.sessions[2].id,epoch:1,answer:'Filed. No approval implied.',evidence:'trusted-operator-exact-benign-fixture',expires:new Date(Date.now()+110000).toISOString()};
  const defs=()=>[
    {id:'read',description:'OFFLINE fake read',input:{type:'object',properties:{path:{type:'string'},offset:{type:'integer'},limit:{type:'integer'}},required:['path']},options:{codemode:false}},
    {id:'write',description:'OFFLINE fake write',input:{type:'object',properties:{path:{type:'string'},content:{type:'string'}},required:['path','content']},options:{codemode:false}},
    {id:'openchamber_knowledge',description:'OFFLINE fake generated managed tool',input:{type:'object',properties:{action:{type:'string',oneOf:[{const:'knowledge.list'},{const:'knowledge.save'}]},parameters:{type:'object',properties:{directory:{type:'string'}},additionalProperties:false}},required:['action'],additionalProperties:true},options:{codemode:false}},
  ];
  const sourcePin=JSON.parse(fs.readFileSync(path.join(root,'bootstrap-source.json')));
  const metadata=()=>{for(const dir of ['home','lead-a','lead-b']) observer({root,directory:path.join(root,dir),source:sourcePin,check:()=>{}}).metadata(defs());};
  return {root,input,write,defs,sourcePin,metadata,report};
}
test('operator inert source staging has no activation, IDs, runtime or native effects',t=>{
  const f=operatorFixture(t),m=JSON.parse(fs.readFileSync(path.join(f.root,'operator-manifest.json')));
  assert.equal(m.phase,'inert');assert.deepEqual(m.sessions,[]);assert.equal(m.goals,false);
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/native-host.json')),false);
  assert.throws(()=>stage(f.root,'/usr/bin/python3',f.sourcePin.source),/EMPTY/);
  assert.throws(()=>strictJSON('{"id":1,"id":2}'),/duplicate/);
});
test('operator pending metadata then complete bound scope accepts global Core IDs, seals source/config/runtime',t=>{
  const f=operatorFixture(t);assert.throws(()=>collect(f.root,f.input),/ENOENT/);f.metadata();
  const steps=collect(f.root,f.input);assert.equal(steps.create.length,4);assert.equal(steps.send.parameters.sessionId,f.input.sessions[2].id);
  const p=preflight({enabled:true,root:f.root,python:'/usr/bin/python3'},{directory:path.join(f.root,'home')});
  assert.equal(p.ready().bindings.length,4);assert.throws(()=>collect(f.root,f.input),/already exists/);
  fs.appendFileSync(path.join(f.root,'home/desk/routes.json'),' ');assert.throws(()=>p.check(),/runtime replaced/);
});
for(const mutation of ['count','duplicate','agent','path','Core','model','scope','disabled','active','epoch','quiescence','response','source','config','symlink']) test('operator all-write preflight refuses '+mutation,t=>{
  const f=operatorFixture(t);f.metadata();
  if(mutation==='count') f.input.sessions.pop();
  if(mutation==='duplicate') f.input.sessions[3].id=f.input.sessions[2].id;
  if(mutation==='agent') f.input.sessions[0].agent='chief';
  if(mutation==='path') f.input.sessions[0].location.directory=f.root;
  if(mutation==='Core') f.input.sessions[0].projectID='wrong-home';
  if(mutation==='model') f.input.sessions[0].model='auto';
  if(mutation==='scope') f.input.knowledge[0].projectId=f.input.knowledge[1].projectId;
  if(mutation==='disabled') f.input.sessions[0].disabled=true;
  if(mutation==='active') f.input.sessions[0].goalActive=true;
  if(mutation==='epoch') f.input.expectedEpoch=2;
  if(mutation==='quiescence') f.input.quiescent=false;
  if(mutation==='response') f.input.sessions[0].response_sha256='a'.repeat(64);
  if(mutation==='source') fs.appendFileSync(path.join(f.root,'fixture-plugin/hosts/desk-native/fixture-observer.mjs'),'// drift');
  if(mutation==='config') fs.appendFileSync(path.join(f.root,'.opencode/opencode.json'),' '); // JSON whitespace not semantic drift: mutate agent instead
  if(mutation==='config') {const c=JSON.parse(fs.readFileSync(path.join(f.root,'.opencode/opencode.json')));c.agents['proof-chief'].steps=99;f.write('.opencode/opencode.json',c);}
  if(mutation==='symlink') fs.symlinkSync('absent',path.join(f.root,'home/chief.json'));
  assert.throws(()=>collect(f.root,f.input));assert.equal(fs.existsSync(path.join(f.root,'home/desk/native-host.json')),false);
});
for(const mutation of ['hash','report','recipient','expiry','epoch','answer','action']) test('exact benign ACK refuses '+mutation,t=>{
  const f=operatorFixture(t);const r=structuredClone(f.input.rule),report=structuredClone(f.report);
  if(mutation==='hash') r.report_hash='a'.repeat(64);
  if(mutation==='report') report.landed+=' mutation';
  if(mutation==='recipient') r.recipient='ses_foreign';
  if(mutation==='expiry') r.expires=new Date(Date.now()-1).toISOString();
  if(mutation==='epoch') r.epoch=2;
  if(mutation==='answer') r.answer='Approved';
  if(mutation==='action') r.action='technical-delegation';
  assert.throws(()=>validateAck(r,report,f.input.sessions[2].id),/ACK rule refused/);
});
test('metadata late pending is metadata ONLY and refuses descriptor alias/disable/drift',t=>{
  const f=operatorFixture(t),o=observer({root:f.root,directory:path.join(f.root,'home'),source:f.sourcePin,check:()=>{}});
  o.metadata([]);assert.equal(fs.existsSync(path.join(f.root,'evidence/metadata-home.json')),false);
  o.metadata(f.defs());assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  assert.throws(()=>o.metadata([{...f.defs()[2],id:'openchamber_knowledge_alias'}]),/alias/);
  assert.throws(()=>o.metadata([{...f.defs()[2],disabled:true}]),/disabled/);
  const defs=f.defs();defs[2].description+=' drift';assert.throws(()=>o.metadata(defs),/changed/);o.stop();
});
test('installed generator optional parameters and action oneOf pass from initial registration',async t=>{
  const f=operatorFixture(t),tools=f.defs().map(t=>({...t,execute:()=>{}}));
  tools[2].input={type:'object',properties:{action:{type:'string',oneOf:[{const:'knowledge.list',description:'List'}]},parameters:{type:'object',properties:{directory:{type:'string'}},additionalProperties:false}},required:['action'],additionalProperties:true};
  const o=observer({root:f.root,directory:path.join(f.root,'lead-a'),source:f.sourcePin,check:()=>{}});t.after(()=>o.stop());
  o.metadata(tools);o.catalog('context',{agent:'proof-lead-a',tools:{desk_report:{}}});
  assert.equal(await o.guard({sessionID:'ses_FAKE',agent:'proof-lead-a',messageID:'msg_FAKE',id:'call_FAKE'},
    {id:'ses_FAKE',agent:'proof-lead-a',projectID:'global',location:{directory:path.join(f.root,'lead-a')}},
    {list:()=>tools,observe:fn=>fn(),probe:async()=>true}),true);
});
test('normalized native created time cannot contradict saved source',t=>{
  const f=operatorFixture(t);f.metadata();f.input.sessions[0].time={created:123};
  assert.throws(()=>collect(f.root,f.input),/time|observation/);
});
for(const mode of ['equal','omitted','updated','missing-created','extra-source']) test('exact native time cross-check '+mode,t=>{
  const f=operatorFixture(t);f.metadata();const s=f.input.sessions[0];
  s.time=mode==='omitted'?{}:{created:123,updated:456};
  const saved=JSON.parse(fs.readFileSync(s.response_file));saved.response.data.sessions[0].time=structuredClone(s.time);
  if(mode==='updated') s.time.updated=789;
  if(mode==='missing-created') delete s.time.created;
  if(mode==='extra-source') saved.response.data.sessions[0].time.foreign=1;
  fs.writeFileSync(s.response_file,JSON.stringify(saved));s.response_sha256=sha(fs.readFileSync(s.response_file));
  if(['equal','omitted'].includes(mode)) collect(f.root,f.input);else assert.throws(()=>collect(f.root,f.input),/time|observation/);
});
for(const mutation of ['action-absent','action-duplicate','action-enum','parameter-required','directory-constraint','top-constraint']) test('fixed Knowledge schema STOP '+mutation,async t=>{
  const f=operatorFixture(t),tools=f.defs().map(t=>({...t,execute:()=>{}})),s=tools[2].input;
  if(mutation==='action-absent') s.properties.action.oneOf=[{const:'knowledge.save'}];
  if(mutation==='action-duplicate') s.properties.action.oneOf.push({const:'knowledge.list'});
  if(mutation==='action-enum') s.properties.action.enum=['knowledge.save'];
  if(mutation==='parameter-required') s.properties.parameters.required=['foreign'];
  if(mutation==='directory-constraint') s.properties.parameters.properties.directory.const='foreign';
  if(mutation==='top-constraint') s.oneOf=[{}];
  const o=observer({root:f.root,directory:path.join(f.root,'lead-a'),source:f.sourcePin,check:()=>{}});t.after(()=>o.stop());
  o.metadata(tools);o.catalog('context',{agent:'proof-lead-a',tools:{desk_report:{}}});let managedProbes=0;
  await assert.rejects(o.guard({sessionID:'ses_FAKE',agent:'proof-lead-a',messageID:'msg_FAKE',id:'call_FAKE'},
    {id:'ses_FAKE',agent:'proof-lead-a',projectID:'global',location:{directory:path.join(f.root,'lead-a')}},
    {list:()=>tools,observe:fn=>fn(),probe:async tool=>{if(tool.id==='openchamber_knowledge') managedProbes++;return true;}}));
  assert.equal(managedProbes,0);
});
for(const mode of ['denied','allowed','missing','unsupported','catalog','pin']) test('captured-context canary fixed args and STOP '+mode,async t=>{
  const f=operatorFixture(t);let calls=0;
  const o=observer({root:f.root,directory:path.join(f.root,'lead-a'),source:f.sourcePin,check:()=>{if(mode==='pin') throw Error('pin drift');}});t.after(()=>o.stop());
  if(mode!=='catalog') o.catalog('context',{agent:'proof-lead-a',tools:{desk_report:{}}});
  const c={sessionID:'ses_FAKE',agent:'proof-lead-a',messageID:'msg_FAKE',id:'call_FAKE'};
  const tools=f.defs().map(t=>({...t,execute:()=>{}}));if(mode==='missing') tools.pop();if(mode==='unsupported') tools[0].input.required.push('unknown');
  const run=()=>o.guard(c,{id:c.sessionID,agent:c.agent,projectID:'global',location:{directory:path.join(f.root,'lead-a')}},{list:()=>tools,observe:fn=>fn(),probe:async(tool,args,actual)=>{
    calls++;assert.equal(actual,c);assert.ok(['read','write','openchamber_knowledge'].includes(tool.id));
    if(tool.id==='write') assert.deepEqual(args,{path:path.join(f.root,'owned-empty-canary'),content:''});return mode!=='allowed';}});
  if(mode==='denied') {assert.equal(await run(),true);assert.equal(await run(),true);assert.equal(calls,3);}
  else await assert.rejects(run());
  assert.equal(fs.statSync(path.join(f.root,'owned-empty-canary')).size,0);
});
for(const mode of ['correct','error-prose','changed-c']) test('OFFLINE FAKE installed-shaped entry: pending metadata -> bind -> actual-c seam -> real SQLite filing/receipt/Notes/evidence '+mode,async t=>{
  const f=operatorFixture(t),contexts=new Map(f.input.sessions.map(s=>[s.id,[]])),notes=new Map(),locations=new Map();let rawGeneric=0,managed=0,expectedContext,nativeReads=0;
  const copied=(await import(pathToFileURL(path.join(f.root,'fixture-plugin/hosts/desk-native/fixture-entry.mjs')).href)).default;
  for(const dir of ['home','lead-a','lead-b']) {
    const tools=new Map(f.defs().map(d=>[d.id,{...d,execute:async(raw,c)=>{
      if(d.id!=='openchamber_knowledge') {rawGeneric++;return {content:''};}
      managed++;assert.equal(c,expectedContext);const {action,parameters:p}=raw,scope=f.input.knowledge.find(k=>k.directory===p.directory)?.projectId;
      const list=notes.get(scope)||[];let data={projectId:scope,notes:list};
      if(action==='knowledge.save') {const note={id:'note_'+notes.size,body:p.body,origin:{sessionId:c.sessionID}};notes.set(scope,[note]);data={projectId:scope,note};}
      return {content:JSON.stringify({schemaVersion:1,ok:true,action,data})};
    }}]));
    const hooks=[];let deliver;const queue=[];
    const ctx={options:{enabled:true,root:f.root,python:'/usr/bin/python3'},location:{directory:path.join(f.root,dir)},
      session:{get:async({sessionID})=>{nativeReads++;const s=f.input.sessions.find(s=>s.id===sessionID);return {...s,model:{providerID:'openai',id:'offline-fake'}};},
        context:async({sessionID})=>structuredClone(contexts.get(sessionID)),hook:async(kind,fn)=>hooks.push({kind,fn}),
        prompt:async p=>{contexts.get(p.sessionID).push({id:p.id,type:'user',text:p.text});return {id:p.id,type:'user',sessionID:p.sessionID,payload:{text:p.text}};},
        synthetic:async p=>{contexts.get(p.sessionID).push({id:p.id,type:'synthetic',text:p.text});return {id:p.id,type:'synthetic',sessionID:p.sessionID,payload:{text:p.text}};}},
      permission:{hook:async()=>{}},tool:{list:async()=>[...tools.values()].map(t=>({...t,execute:(raw,c)=>{
        if(t.id==='read' && mode==='error-prose') throw Error('generic executor denied for native desk role');
        return t.execute(raw,t.id==='read' && mode==='changed-c'?{...c,id:'changed-call'}:c);
      }})),
        transform:async fn=>fn({list:()=>[...tools.values()],update:(id,fn)=>fn(tools.get(id)),add:t=>tools.set(t.name,{...t,id:t.name})})},
      event:{subscribe:({signal})=>(async function*(){signal.addEventListener('abort',()=>deliver?.(),{once:true});while(!signal.aborted) {if(!queue.length) await new Promise(r=>deliver=r);if(signal.aborted) break;const x=queue.shift();yield x.event;x.done();}})()}};
    const cleanup=await copied.setup(ctx);t.after(cleanup);
    locations.set(dir,{ctx,tools,hooks,cleanup,event:sessionID=>new Promise(done=>{queue.push({event:{type:'session.execution.succeeded',data:{sessionID}},done});deliver?.();})});
  }
  // Descriptor bootstrap performs no native get/bridge/managed operation while pending.
  assert.equal(managed,0);assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  const pendingC={agent:'proof-lead-a',sessionID:f.input.sessions[2].id,messageID:'msg_pendingFAKE',id:'call_pendingFAKE',signal:new AbortController().signal};
  await assert.rejects(locations.get('lead-a').tools.get('desk_report').execute({report:f.report},pendingC),/ENOENT/);
  assert.equal(nativeReads,0);
  await assert.rejects(locations.get('lead-a').tools.get('openchamber_knowledge').execute({action:'knowledge.list',parameters:{directory:path.join(f.root,'lead-a')},__deskHostTicket:'model-invented'},pendingC),/invalid host capability/);
  assert.equal(managed,0);
  collect(f.root,f.input);
  await assert.rejects(locations.get('lead-a').tools.get('desk_report').execute({report:f.report,verified:true,probe:()=>true},pendingC),/unexpected tool arguments/);
  assert.equal(nativeReads,0);assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  async function call(dir,agent,name,args,number) {
    const l=locations.get(dir),s=f.input.sessions.find(s=>s.agent===agent),c={sessionID:s.id,agent,messageID:'msg_FAKE'+number,id:'call_FAKE'+number,signal:new AbortController().signal};
    const catalog=Object.fromEntries([...l.tools.keys()].map(n=>[n,{}]));for(const h of l.hooks) h.fn({agent,tools:catalog});
    expectedContext=c;const raw=await l.tools.get(name).execute(args,c),result=JSON.parse(raw.content);
    contexts.get(s.id).push({id:c.messageID,type:'assistant',content:[{type:'tool',id:c.id,name,state:{status:'completed',input:args,output:raw.content}}]});
    await l.event(s.id);return result;
  }
  if(mode!=='correct') {
    await assert.rejects(call('lead-a','proof-lead-a','desk_report',{report:f.report},1),/canary unexpectedly allowed\/unknown/);
    assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);assert.equal(managed,0);
    await assert.rejects(locations.get('home').tools.get('desk_inbox').execute({inputId:'unknown'},
      {agent:'proof-desk',sessionID:f.input.sessions[0].id,messageID:'msg_sibling',id:'call_sibling',signal:new AbortController().signal}),/stopped|unresolved/);
    return;
  }
  const reported=await call('lead-a','proof-lead-a','desk_report',{report:f.report},1);
  const filed=await call('home','proof-desk','desk_inbox',{inputId:reported.inputId},2);
  assert.equal(filed.filed,true);assert.equal(managed,6);assert.equal(rawGeneric,0);assert.equal(notes.size,2);
  await locations.get('lead-a').event(f.input.sessions[2].id);
  const binding=JSON.parse(fs.readFileSync(path.join(f.root,'evidence/binding-manifest.json'))),logs=['home','lead-a'].map(d=>JSON.parse(fs.readFileSync(path.join(f.root,'evidence',d+'.json'))));
  assert.equal(validateSmoke(binding,logs).state,'correlated-first-smoke-only');
  for(const corrupt of ['both-summary-ids','native-input-output','watermark','foreign-empty-list','prompt-admission']) await t.test('contradictory chain '+corrupt,()=>{
    const bad=structuredClone(logs),all=bad.flatMap(l=>l.events),rows=op=>all.filter(e=>e.kind==='bridge'&&e.data.op===op);
    if(corrupt==='both-summary-ids') for(const op of ['note_returned','note_reconcile']) for(const e of rows(op)) e.data.value.note_id='note_FORGED';
    if(corrupt==='native-input-output') for(const e of all.filter(e=>e.kind==='native'&&e.data.op==='context')) for(const m of e.data.value) for(const p of m.content||[]) if(p.type==='tool') {p.state.input={FORGED:true};p.state.output='FORGED';}
    if(corrupt==='watermark') for(const e of rows('note_reconcile')) e.data.value.watermark=999999;
    if(corrupt==='foreign-empty-list') for(const e of rows('note_reconcile')) e.data.input.listing={projectId:'foreign',notes:[]};
    if(corrupt==='prompt-admission') {const d=all.find(e=>e.kind==='native'&&e.data.op==='prompt').data;d.input.sessionID='ses_foreign';d.input.id='msg_foreign';d.value={};}
    assert.equal(validateSmoke(binding,bad).state,'unknown-STOP');
  });
  for(const corrupt of ['missing-prepare','duplicate-return','duplicate-action-kind','tool-output','tool-call','tool-message','native-model',
    'managed-input','managed-output','managed-caller','saved-body','saved-origin','duplicate-list-id','returned-id',
    'intent-nonce','intent-watermark','ledger-watermark','ledger-note','ledger-action','missing-ledger','all-summary-watermarks','list-before-return',
    'extra-caller','duplicate-tool-part','conflicting-readback']) await t.test('exact join STOP '+corrupt,()=>{
    const bad=structuredClone(logs),all=bad.flatMap(l=>l.events),find=(kind,op)=>all.find(e=>e.kind===kind&&e.data.op===op);
    const remove=e=>{const l=bad.find(l=>l.events.includes(e));l.events.splice(l.events.indexOf(e),1);l.events.forEach((e,i)=>e.seq=i+1);};
    if(corrupt==='missing-prepare') remove(find('bridge','note_prepare'));
    if(corrupt==='duplicate-return') {const l=bad[0];l.events.push({...structuredClone(find('bridge','note_returned')),seq:l.events.length+1,at:l.events.at(-1).at});}
    if(corrupt==='duplicate-action-kind') find('bridge','file_input').data.value.actions[0].kind='receipt';
    if(['tool-output','tool-call','tool-message'].includes(corrupt)) for(const e of all.filter(e=>e.kind==='native'&&e.data.op==='context')) for(const m of e.data.value) for(const p of m.content||[]) {
      if(corrupt==='tool-output') p.state.output='FORGED';if(corrupt==='tool-call') p.id='foreign';if(corrupt==='tool-message') m.id='foreign';
    }
    if(corrupt==='native-model') find('native','get').data.value.model.id='foreign';
    if(corrupt==='managed-input') find('managed','knowledge.save').data.input.parameters.body='FORGED';
    if(corrupt==='managed-output') find('managed','knowledge.save').data.value.note.id='FORGED';
    if(corrupt==='managed-caller') find('managed','knowledge.save').data.input.call.id='foreign';
    if(corrupt==='saved-body') find('bridge','note_returned').data.input.saved.note.body='FORGED';
    if(corrupt==='saved-origin') find('bridge','note_returned').data.input.saved.note.origin.sessionId='foreign';
    if(corrupt==='duplicate-list-id') {const l=find('bridge','note_reconcile').data.input.listing.notes;l.push(structuredClone(l[0]));}
    if(corrupt==='returned-id') find('bridge','note_returned').data.input.saved.note.id='foreign';
    if(corrupt==='intent-nonce') find('bridge','note_prepare').data.value.nonce='a'.repeat(32);
    if(corrupt==='intent-watermark') find('bridge','note_prepare').data.value.watermark=999999;
    if(corrupt==='ledger-watermark') find('bridge','smoke_state').data.value.watermark=999999;
    if(corrupt==='ledger-note') find('bridge','smoke_state').data.value.notes['lead-a'].note_id='foreign';
    if(corrupt==='ledger-action') find('bridge','smoke_state').data.value.actions.pop();
    if(corrupt==='missing-ledger') remove(find('bridge','smoke_state'));
    if(corrupt==='extra-caller') {const l=bad[0];l.events.push({...structuredClone(all.find(e=>e.kind==='native-caller')),seq:l.events.length+1,at:l.events.at(-1).at});}
    if(corrupt==='duplicate-tool-part') for(const e of all.filter(e=>e.kind==='native'&&e.data.op==='context')) for(const m of e.data.value) if(m.content?.length) m.content.push(structuredClone(m.content[0]));
    if(corrupt==='conflicting-readback') {const e=all.find(e=>e.kind==='native'&&e.data.op==='context'&&e.data.value.some(m=>m.type==='synthetic'));e.data.value.find(m=>m.type==='synthetic').text='FORGED';}
    if(corrupt==='all-summary-watermarks') for(const e of all.filter(e=>e.kind==='bridge'&&['note_prepare','note_returned','note_reconcile'].includes(e.data.op))) e.data.value.watermark=999999;
    if(corrupt==='list-before-return') {const l=bad[0],a=l.events.indexOf(find('bridge','note_returned')),z=l.events.indexOf(find('bridge','note_reconcile'));[l.events[a],l.events[z]]=[l.events[z],l.events[a]];l.events.forEach((e,i)=>{e.seq=i+1;e.at=l.events[0].at+i;});}
    assert.equal(validateSmoke(binding,bad).state,'unknown-STOP',corrupt);
  });
  for(const corrupt of ['missing','compacted','outward','interleaved','note','duplicate','identity']) {
    const bad=structuredClone(logs),all=bad.flatMap(l=>l.events);
    if(corrupt==='missing') bad[0].events.shift();
    if(corrupt==='compacted') for(const e of all) if(e.kind==='native'&&e.data.op==='context') e.data.value=[];
    if(corrupt==='outward') all.find(e=>e.kind==='native'&&e.data.op==='synthetic').data.input.sessionID='ses_foreign';
    if(corrupt==='interleaved') all[0].kind='unknown';
    if(corrupt==='note') all.find(e=>e.kind==='bridge'&&e.data.op==='note_returned').data.value.note_id='foreign';
    if(corrupt==='duplicate') bad[1].events.push({...bad[1].events.find(e=>e.kind==='registered-tool'&&e.data.op==='desk_report'),seq:bad[1].events.length+1});
    if(corrupt==='identity') all.find(e=>e.kind==='native-caller').data.native.projectID='foreign';
    assert.equal(validateSmoke(binding,bad).state,'unknown-STOP',corrupt);
  }
  // Cleanup fences all locations; no replacement runtime or late replay.
  const stopped=await locations.get('home').cleanup();assert.equal(stopped.unresolved,0);
  await assert.rejects(copied.setup(locations.get('home').ctx),/no replacement/);
  assert.equal(fs.statSync(path.join(f.root,'owned-empty-canary')).size,0);
});
test('private captures/evidence caps and linked evidence refuse with no outside write',async t=>{
  const f=operatorFixture(t),o=observer({root:f.root,directory:path.join(f.root,'home'),source:f.sourcePin,check:()=>{}});t.after(()=>o.stop());
  for(let i=0;i<128;i++) o.record('OFFLINE-FAKE',{i});
  assert.throws(()=>o.record('OFFLINE-FAKE',{}),/cap/);
  const outside=path.join(path.dirname(f.root),'outside-untouched');fs.writeFileSync(outside,'untouched',{mode:0o600});
  fs.symlinkSync(outside,path.join(f.root,'evidence/lead-a.json'));
  assert.throws(()=>observer({root:f.root,directory:path.join(f.root,'lead-a'),source:f.sourcePin,check:()=>{}}),/existing evidence/);
  assert.equal(fs.readFileSync(outside,'utf8'),'untouched');
  const p=preflight({enabled:true,root:f.root,python:'/usr/bin/python3'},{directory:path.join(f.root,'home')});
  for(let i=0;i<16;i++) p.capture('OFFLINE-FAKE',{});
  assert.throws(()=>p.capture('OFFLINE-FAKE',{}),/cap/);p.release();p.capture('OFFLINE-FAKE',{});p.release();
});
function fixture(t,ancestor=false) {
  const owned=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'desk-entry-')));
  t.after(()=>fs.rmSync(owned,{recursive:true,force:true}));
  const root=ancestor?path.join(owned,'F'):owned;
  if(ancestor) {
    fs.mkdirSync(root,{mode:0o700});
    // Owned synthetic ancestor only, NEVER read/write private global settings.
    fs.writeFileSync(path.join(owned,'opencode.json'),JSON.stringify({agents:{'proof-chief':{permissions:[{effect:'allow',action:'*',resource:'*'}]}}}),{mode:0o600});
  }
  const write=(f,v)=>{const p=path.join(root,f);fs.mkdirSync(path.dirname(p),{recursive:true,mode:0o700});fs.writeFileSync(p,JSON.stringify(v),{mode:0o600});};
  for (const d of ['home/desk','lead-a','lead-b','fixture-plugin','.opencode']) fs.mkdirSync(path.join(root,d),{recursive:true,mode:0o700});
  const inventory={};
  for (const f of fixtureAssets) {
    const original=f==='scripts/progress.template.html'?'kits/chief/desk/progress.template.html':f;
    const bytes=fs.readFileSync(new URL(original,source));
    write('fixture-plugin/'+f,null);fs.writeFileSync(path.join(root,'fixture-plugin',f),bytes);
    inventory[f]=createHash('sha256').update(bytes).digest('hex');
  }
  write('fixture-plugin/fixture-source.json',inventory);
  write('fixture-plugin/package.json',JSON.parse(fs.readFileSync(new URL('hosts/desk-native/fixture-package.json',source))));
  const options={enabled:true,root,python:'/usr/bin/python3'}, location={directory:path.join(root,'home')};
  const config=pendingConfig(root,options.python);config.plugins[0].options.enabled=true;write('.opencode/opencode.json',config);
  const host={version:1,enabled:true,desk_agent:'proof-desk',chief_agent:'proof-chief',home_nativeProjectID:'core_home',home_projectId:'knowledge_home',overview_create:true,projects:{}};
  write('managed-source.mjs','offline source fixture');
  host.knowledge={source:path.join(root,'managed-source.mjs'),sha256:createHash('sha256').update(fs.readFileSync(path.join(root,'managed-source.mjs'))).digest('hex'),descriptor_sha256:'a'.repeat(64)};
  const registry={version:1,projects:{},rules:{}},routes={version:1,projects:{}};
  for(const dir of ['lead-a','lead-b']) {
    host.projects[dir]={enabled:true,lead_agent:'proof-'+dir,nativeProjectID:'core_'+dir,projectId:'knowledge_'+dir,note_create:true};
    registry.projects[dir]={path:path.join(root,dir),log:path.join(root,dir,'LEAD.md'),leads:['ses_'+dir.replace('-','')]};
    routes.projects[dir]={enabled:true,epoch:1,leads:registry.projects[dir].leads};
  }
  write('home/desk/native-host.json',host);write('home/desk/registry.json',registry);write('home/desk/routes.json',routes);
  for(const role of ['desk','chief']) write('home/'+role+'.json',{session:'ses_'+role,directory:location.directory,updated:'fixture'});
  return {root,write,host,registry,routes,config,options,location};
}
test('entry is a private disabled-by-default installed-shaped definition',async()=>{
  assert.equal(entry.id,'chief-desk-native-fixture');
  await entry.setup({options:{},get location(){throw Error('default touched location');}});
  const c=pendingConfig('/fixture','/usr/bin/python3');
  assert.equal(c.plugins[0].options.enabled,false);assert.equal(Object.keys(c.agents).length,4);
  for(const agent of Object.values(c.agents)) assert.equal(agent.permissions[0].effect,'deny');
});
test('preflight exact scope; fake test IDs are not native authority',t=>{
  const f=fixture(t),p=preflight(f.options,f.location);assert.equal(p.ready().bindings.length,4);p.check();
  assert.throws(()=>p.caller({sessionID:'ses_chief',agent:'proof-chief'},{}),/native caller refused/);
  assert.throws(()=>preflight(f.options,{directory:f.root}),/location refused/);
  assert.throws(()=>preflight({...f.options,token:'no'},f.location),/exact fixture options/);
});
test('source/config replacement, permissive parent and symlink fail closed',t=>{
  const f=fixture(t),p=preflight(f.options,f.location);
  fs.chmodSync(path.join(f.root,'fixture-plugin/hosts'),0o755);assert.throws(()=>p.check(),/private owned/);
  fs.chmodSync(path.join(f.root,'fixture-plugin/hosts'),0o700);
  const sourcePath=path.join(f.root,'fixture-plugin/hosts/desk-native/index.mjs'),original=fs.readFileSync(sourcePath);
  fs.appendFileSync(sourcePath,'// replaced');assert.throws(()=>p.check(),/replaced/);fs.writeFileSync(sourcePath,original);
  fs.unlinkSync(path.join(f.root,'home/chief.json'));fs.symlinkSync('desk.json',path.join(f.root,'home/chief.json'));
  assert.throws(()=>preflight(f.options,f.location).ready(),/canonical nonlinked/);
});
for(const variant of ['pending','scope-collision','foreign-role','rule','git-root','package']) test('preflight refuses '+variant,t=>{
  const f=fixture(t);
  if(variant==='pending') {delete f.host.home_nativeProjectID;f.write('home/desk/native-host.json',f.host);}
  if(variant==='scope-collision') {f.host.projects['lead-a'].projectId=f.host.home_projectId;f.write('home/desk/native-host.json',f.host);}
  if(variant==='foreign-role') {f.host.chief_agent='production-chief';f.write('home/desk/native-host.json',f.host);}
  if(variant==='rule') {f.registry.rules.arbitrary={};f.write('home/desk/registry.json',f.registry);}
  if(variant==='git-root') fs.mkdirSync(path.join(f.root,'.git'));
  if(variant==='package') f.write('fixture-plugin/package.json',{private:false});
  assert.throws(()=>preflight(f.options,f.location).ready());
});
test('executing source outside the pinned package cannot admit native reads',async t=>{
  const f=fixture(t);let calls=0;
  await assert.rejects(entry.setup({options:f.options,location:f.location,session:{get(){calls++;}}}),/pinned fixture package/);
  assert.equal(calls,0);
});
test('fixed registration: pending refuses writes, trusted bind needs native identity, cleanup tombstones new ctx',async t=>{
  const f=fixture(t);
  const {pathToFileURL}=await import('node:url');
  const url=pathToFileURL(path.join(f.root,'fixture-plugin/hosts/desk-native/fixture-entry.mjs')).href;
  const copied=(await import(url)).default;let calls=0;
  const paths=['home/desk/native-host.json','home/desk/registry.json','home/desk/routes.json','home/desk.json','home/chief.json'];
  const runtime=paths.map(p=>fs.readFileSync(path.join(f.root,p)));
  for(const p of paths) fs.unlinkSync(path.join(f.root,p));
  const tools=new Map([['shell',{id:'shell',execute:async()=>{throw Error('raw generic reached');}}]]),hooks=[];
  const ctx={options:f.options,location:f.location,
    session:{get:async()=>{calls++;return {id:'ses_forged'};},hook:async(k,fn)=>{hooks.push(fn);}},
    permission:{hook:async()=>{}},
    tool:{transform:async fn=>fn({list:()=>[...tools.values()],update:(id,fn)=>fn(tools.get(id)),add:t=>tools.set(t.name,{...t,id:t.name})})},
    event:{subscribe:({signal})=>(async function*(){if(!signal.aborted) await new Promise(resolve=>signal.addEventListener('abort',resolve,{once:true}));})()},
  };
  const cleanup=await copied.setup(ctx);assert.equal(calls,0);assert.equal(hooks.length,3);assert.ok(tools.has('desk_decision'));
  for(const hook of hooks) {const event={agent:'proof-lead-a',tools:{desk_report:{},shell:{}}};hook(event);assert.deepEqual(event.tools,{});}
  await assert.rejects(tools.get('desk_report').execute({}, {agent:'proof-lead-a',signal:new AbortController().signal}),/role\/location denied/);
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  const c={agent:'proof-chief',sessionID:'ses_chief',messageID:'msg_actualshape',id:'tool_fixture',signal:new AbortController().signal};
  const args={project:'lead-a',sourceReceipt:1,itemKey:'x',expectedRevision:0,state:'open',decisionText:'not approval'};
  await assert.rejects(tools.get('desk_decision').execute(args,c),/ENOENT/);assert.equal(calls,0);
  paths.forEach((p,i)=>fs.writeFileSync(path.join(f.root,p),runtime[i],{mode:0o600}));
  await assert.rejects(tools.get('desk_decision').execute(args,c),/native session unavailable/);assert.equal(calls,1);
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  await cleanup();
  const replaced=(await import(url+'?fresh-module')).default;
  await assert.rejects(replaced.setup({...ctx}),/no replacement/);assert.equal(calls,1);
});
test('runtime binds once without descriptor/config reload and rejects later mutation',t=>{
  const f=fixture(t),p=preflight(f.options,f.location);
  assert.equal(p.isReady(),false);assert.equal(p.config().chief_agent,'proof-chief');
  p.ready();assert.equal(p.isReady(),true);
  const b=p.ready().bindings.find(b=>b.agent==='proof-chief');
  p.caller({sessionID:b.sessionID,agent:b.agent},{id:b.sessionID,agent:b.agent,projectID:b.projectID,location:{directory:b.directory},time:{}});
  f.host.home_nativeProjectID='forged';f.write('home/desk/native-host.json',f.host);
  assert.throws(()=>p.ready(),/runtime replaced/);
});

// Real copied entry and private Python/SQLite effects; native context/IDs are fakes.
async function loaded(t,f,{valid=false,onGet=()=>{}}={}) {
  let reads=0,effects=0,deliver;
  const queue=[];const tools=new Map([['shell',{id:'shell',execute:async()=>{effects++;}}],
    ['openchamber_knowledge',{id:'openchamber_knowledge',execute:async()=>{effects++;}}]]);
  const ctx={options:f.options,location:f.location,
    session:{get:async({sessionID})=>{reads++;onGet();return valid ? {id:sessionID,agent:'proof-chief',projectID:'core_home',location:f.location,time:{}} : {id:'ses_forged'};},
      hook:async()=>{},prompt:async()=>{effects++;},synthetic:async()=>{effects++;}},
    permission:{hook:async()=>{}},
    tool:{transform:async fn=>fn({list:()=>[...tools.values()],update:(id,fn)=>fn(tools.get(id)),add:t=>tools.set(t.name,{...t,id:t.name})})},
    event:{subscribe:({signal})=>(async function*(){
      signal.addEventListener('abort',()=>deliver?.(),{once:true});
      while(!signal.aborted) {
        if(!queue.length) await new Promise(r=>{deliver=r;});
        if(signal.aborted) break;
        const {event,done}=queue.shift();yield event;done();
      }
    })()},
  };
  const copied=(await import(pathToFileURL(path.join(f.root,'fixture-plugin/hosts/desk-native/fixture-entry.mjs')).href)).default;
  const cleanup=await copied.setup(ctx);t.after(cleanup);
  return {tools,cleanup,get reads(){return reads;},get effects(){return effects;},
    event:type=>new Promise(done=>{queue.push({event:{type},done});deliver?.();}),
    call:()=>tools.get('desk_decision').execute({project:'lead-a',sourceReceipt:1,itemKey:'x',expectedRevision:0,state:'open',decisionText:'not approval'},
      {agent:'proof-chief',sessionID:'ses_chief',messageID:'msg_fake',id:'tool_fake',signal:new AbortController().signal})};
}
for(const drift of [false,true]) test('E1 failed identity then event never creates a store; pin drift='+drift,async t=>{
  const f=fixture(t),l=await loaded(t,f);
  await assert.rejects(l.call(),/native session unavailable/);assert.equal(l.reads,1);
  if(drift) fs.appendFileSync(path.join(f.root,'.opencode/opencode.json'),' ');
  await l.event('server.connected');
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  assert.equal(l.reads,1);assert.equal(l.effects,0);
  await assert.rejects(l.call(),drift ? /pinned source\/config/ : /native session unavailable/);
});
test('E1 sealed valid fixture without operator bootstrap stays pending, no automatic recovery',async t=>{
  const f=fixture(t),l=await loaded(t,f,{valid:true});
  await assert.rejects(l.call(),/bootstrap pending/);
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  fs.appendFileSync(path.join(f.root,'.opencode/opencode.json'),' ');
  await l.event('server.connected');await l.event('session.execution.succeeded');
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);
  await assert.rejects(l.call(),/pinned source\/config/);assert.equal(l.effects,0);
});
for(const pin of ['.opencode/opencode.json','fixture-plugin/scripts/desk_native.py','home/desk/routes.json'])
test('E1 pin changes during successful native get refuse before bridge: '+pin,async t=>{
  const f=fixture(t),l=await loaded(t,f,{valid:true,onGet:()=>fs.appendFileSync(path.join(f.root,pin),' ')});
  await assert.rejects(l.call(),/replaced/);
  assert.equal(fs.existsSync(path.join(f.root,'home/desk/store.sqlite')),false);assert.equal(l.effects,0);
});
const discovered=['opencode.json','opencode.jsonc','.opencode/opencode.json','.opencode/opencode.jsonc',
  ...['agent','agents','mode','modes','plugin','plugins','command','commands','skill','skills'].map(d=>'.opencode/'+d),'.agents','.claude'];
for(const base of ['','home/','lead-a/','lead-b/','fixture-plugin/'])
for(const name of discovered) for(const phase of ['before','after']) {
  if(base==='' && name==='.opencode/opencode.json') continue;
  test('E2 rejects discovered input '+phase+' preflight: '+base+name,t=>{
    const f=fixture(t),p=phase==='after'?preflight(f.options,f.location):null,relative=base+name;
    p?.ready(); // Drift after completed checks/sealing must still refuse.
    const value={agents:{'proof-chief':{permissions:[{effect:'allow',action:'*',resource:'*'}]}}};
    if(name.endsWith('.json') || name.endsWith('.jsonc')) f.write(relative,value);
    else f.write(relative+'/unexpected/'+(name.endsWith('plugin')||name.endsWith('plugins')?'package.json':'definition.md'),value);
    if(p) {assert.throws(()=>p.check(),/discovery/);assert.throws(()=>p.ready(),/discovery/);}
    else assert.throws(()=>preflight(f.options,f.location),/discovery/);
  });
}
for(const kind of ['symlink','dangling','hardlink','directory','parent-link']) test('E2 no following unexpected '+kind,t=>{
  const f=fixture(t),p=preflight(f.options,f.location),target=path.join(f.root,'home/.opencode');
  if(kind==='parent-link') fs.symlinkSync(path.join(f.root,'.opencode'),target);
  else {
    fs.mkdirSync(target,{mode:0o700});const dest=path.join(target,'opencode.jsonc');
    if(kind==='directory') fs.mkdirSync(dest,{mode:0o700});
    else if(kind==='hardlink') fs.linkSync(path.join(f.root,'.opencode/opencode.json'),dest);
    else fs.symlinkSync(kind==='dangling'?'absent':path.join(f.root,'.opencode/opencode.json'),dest);
  }
  assert.throws(()=>p.check());assert.throws(()=>preflight(f.options,f.location));
});
test('E2 ordinary generated runtime/log/store/evidence are not discovery inputs; ancestors are a trust assumption',t=>{
  const f=fixture(t,true),p=preflight(f.options,f.location);
  for(const name of ['home/desk/store.sqlite','home/logs/output.log','lead-a/evidence/result.json','.opencode/logs/run.log','fixture-plugin/build.log']) f.write(name,{});
  p.check();p.ready();p.check();
  // No ancestor/global private config is read. Those layers are NOT attested here.
  assert.equal(p.config().chief_agent,'proof-chief');
});
for(const kind of ['hardlink','symlink','writable','replacement']) test('E2 expected config retains exact path/file safety: '+kind,t=>{
  const f=fixture(t),p=preflight(f.options,f.location),config=path.join(f.root,'.opencode/opencode.json');
  if(kind==='hardlink') fs.linkSync(config,path.join(f.root,'ordinary-copy'));
  if(kind==='symlink') {fs.renameSync(config,config+'.saved');fs.symlinkSync(config+'.saved',config);}
  if(kind==='writable') fs.chmodSync(config,0o620);
  if(kind==='replacement') {fs.renameSync(config,config+'.saved');f.write('.opencode/opencode.json',{agents:{}});}
  assert.throws(()=>p.check());assert.throws(()=>preflight(f.options,f.location));
});
