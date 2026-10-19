// Offline installed-shaped ctx/managed wrapper fixtures, NOT native acceptance.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {makePlugin,descriptorHash,filter} from '../hosts/desk-native/index.mjs';
import {bridge} from '../hosts/desk-native/bridge.mjs';
import {permissions} from '../hosts/desk-native/catalog.mjs';
import {observeOwnedProof} from '../scripts/desk_native_proof.mjs';

const hash=x=>createHash('sha256').update(x).digest('hex');
async function fixture(t,dependencies={},beforeSetup=()=>{}) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'desk-native-node-')));
  // Exact generated fixture root only; never follows links/removes project files.
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const home=path.join(root,'home'),project=path.join(root,'project');
  fs.mkdirSync(path.join(home,'desk'),{recursive:true});fs.mkdirSync(project);
  const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v));
  save(path.join(home,'desk/registry.json'),{version:1,projects:{fixture:{path:project,log:path.join(project,'LEAD.md'),leads:['ses_lead']}},rules:{}});
  save(path.join(home,'desk/routes.json'),{version:1,projects:{fixture:{enabled:true,epoch:1,leads:['ses_lead']}}});
  for(const name of ['chief','desk']) save(path.join(home,name+'.json'),{session:'ses_'+name,directory:home,updated:'2026-10-01T00:00:00Z'});
  const notes=new Map([[project,[]],[home,[]]]),managedCalls=[];
  const managed={id:'openchamber_knowledge',description:'Installed-shaped managed Knowledge fixture',
    options:{codemode:false},input:{type:'object',properties:{action:{type:'string'},parameters:{type:'object'}},required:['action'],additionalProperties:true},
    execute:async ({action,parameters:p},c)=>{
      managedCalls.push({action,parameters:p,sessionID:c.sessionID});
      let data;
      const projectId=p.directory===home?'path_home':'path_project';
      if(action==='knowledge.list') data={projectId,notes:notes.get(p.directory),todos:[],plans:[]};
      else if(action==='knowledge.save') {
        assert.equal(p.kind,'note');assert.equal(c.sessionID,'ses_desk');
        let note;
        if(p.id) {
          note=notes.get(p.directory).find(n=>n.id===p.id);
          if(!note || note.body!==p.expected) return {content:JSON.stringify({schemaVersion:1,ok:false,action,error:{message:'conflict'}})};
          note.body=p.body.trim();
        } else {note={id:'note_'+notes.get(p.directory).length,body:p.body.trim(),source:'agent',origin:{sessionId:c.sessionID}};notes.get(p.directory).push(note);}
        data={projectId,note};
      } else throw Error('unexpected operation');
      return {content:JSON.stringify({schemaVersion:1,ok:true,action,data})};
    }};
  const pinSource=path.join(root,'managed-source.mjs');fs.writeFileSync(pinSource,'// Fixture descriptor source, no auth\n');
  const cfg={version:1,enabled:true,desk_agent:'native-desk',chief_agent:'native-chief',home_projectId:'path_home',home_nativeProjectID:'core_home',overview_create:true,
    projects:{fixture:{enabled:true,lead_agent:'native-lead',projectId:'path_project',nativeProjectID:'core_project',note_create:true}},
    knowledge:{source:pinSource,sha256:hash(fs.readFileSync(pinSource)),descriptor_sha256:descriptorHash(managed)}};
  const configPath=path.join(home,'desk/native-host.json');save(configPath,cfg);
  const info=new Map(['lead','desk','chief'].map(r=>['ses_'+r,{id:'ses_'+r,agent:'native-'+r,projectID:r==='lead'?'core_project':'core_home',location:{directory:r==='lead'?project:home},time:{created:1}}]));
  const messages=new Map([...info.keys()].map(id=>[id,[]])), admissions=[];
  const tools=new Map([[managed.id,managed],['shell',{id:'shell',description:'generic',execute:async()=>{throw Error('raw shell reached');}}]]);
  const hooks=[],permissionHooks=[];
  const native=type=>async input=>{
    assert.ok(/^msg_/.test(input.id));
    const record={id:input.id,type,text:input.text,metadata:input.metadata,time:{created:1}};
    messages.get(input.sessionID).push(record);
    const admission={id:input.id,sessionID:input.sessionID,type,payload:{text:input.text,metadata:input.metadata},delivery:input.delivery,time:{created:1}};
    admissions.push(admission);return admission;
  };
  const ctx={
    session:{get:async ({sessionID})=>info.get(sessionID),context:async ({sessionID})=>messages.get(sessionID),
      prompt:native('user'),synthetic:native('synthetic'),hook:async(k,fn)=>{hooks.push({k,fn});}},
    permission:{hook:async(k,fn)=>{permissionHooks.push(fn);}},
    tool:{list:async()=>[...tools.values()].map(t=>({...t,execute:(...args)=>t.execute(...args)})),transform:async fn=>fn({list:()=>[...tools.values()],update:(id,fn)=>fn(tools.get(id)),add:tool=>tools.set(tool.name,{...tool,id:tool.name})})},
    event:{subscribe:({signal})=>(async function*(){if(!signal.aborted) await new Promise(resolve=>signal.addEventListener('abort',resolve,{once:true}));})()},
  };
  const invoke=bridge({home,python:'/usr/bin/python3'});
  if (dependencies.fixture) Object.assign(dependencies.fixture,{config:()=>cfg,ready:()=>{},isReady:()=>true});
  beforeSetup(ctx);
  const cleanup=await makePlugin({enabled:true,home,python:'/usr/bin/python3'},dependencies).setup(ctx);
  t.after(cleanup);
  let n=0;
  const call=async (name,raw,r,signal=new AbortController().signal)=>tools.get(name).execute(raw,{sessionID:'ses_'+r,agent:'native-'+r,messageID:'msg_assistant_'+(++n),id:'tool'+n,signal,progress:async()=>{}});
  const report={project:'fixture',id:'r1',source_revision:1,observed:'2026-10-01T00:00:00Z',landed:'Ready',next:'Review',your_part:null,state:'active',request:'May I publish?',rule:''};
  return {ctx,home,project,cfg,save,configPath,info,messages,admissions,tools,managedCalls,notes,invoke,call,report,hooks,permissionHooks,cleanup};
}

test('disabled adapter does not touch catalogs/context',async()=>{
  let touched=false;await makePlugin({enabled:false}).setup(new Proxy({},{get(){touched=true;throw Error();}}));assert.equal(touched,false);
});
test('fixture strict chief and unknown roles lose every generic executor and all three catalogs',async t=>{
  let valid=true;
  const f=await fixture(t,{fixture:{check(){if(!valid) throw Error('fixture replaced');},caller(){}}});
  for(const agent of ['native-chief','unknown']) {
    for(const {k,fn} of f.hooks) {
      assert.ok(['context','generate','compaction'].includes(k));
      const event={agent,tools:Object.fromEntries(f.tools)};fn(event);
      assert.deepEqual(Object.keys(event.tools),agent==='native-chief'?['desk_decision']:[]);
    }
    for(const name of ['shell','openchamber_knowledge']) await assert.rejects(f.call(name,{},agent==='native-chief'?'chief':'unknown'),/generic executor denied/);
    const event={agent,action:'openchamber_knowledge'};f.permissionHooks[0](event);assert.equal(event.effect,'deny');
  }
  valid=false;
  const event={agent:'native-chief',tools:Object.fromEntries(f.tools)};
  assert.throws(()=>f.hooks[0].fn(event),/fixture replaced/);assert.deepEqual(event.tools,{});
  await assert.rejects(f.call('desk_decision',{},'chief'),/fixture replaced|unexpected tool/);
});
test('nonfixture real chief generic execution remains unchanged',async t=>{
  const f=await fixture(t);
  // Original shell deliberately throws this marker: reaching it proves preservation.
  await assert.rejects(f.call('shell',{},'chief'),/raw shell reached/);
  const event={agent:'native-chief',tools:{shell:{},desk_report:{},desk_decision:{}}};
  f.hooks[0].fn(event);assert.deepEqual(Object.keys(event.tools),['shell','desk_decision']);
});
for(const strict of [false,true]) test('automatic reconciliation policy: '+(strict?'fixture disabled':'production unchanged'),async t=>{
  let bridges=0,deliver;const queue=[];
  const f=await fixture(t,{...(strict?{fixture:{check(){},caller(){}}}:{}),
    invoke:async op=>{assert.equal(op,'pending');bridges++;return {inputs:[],actions:[]};}},ctx=>{
      ctx.event.subscribe=({signal})=>(async function*(){
        signal.addEventListener('abort',()=>deliver?.(),{once:true});
        while(!signal.aborted) {
          if(!queue.length) await new Promise(r=>{deliver=r;});
          if(signal.aborted) break;
          const done=queue.shift();yield {type:'server.connected'};done();
        }
      })();
    });
  assert.equal(bridges,strict?0:1);
  await new Promise(done=>{queue.push(done);deliver?.();});
  assert.equal(bridges,strict?0:2);
  assert.equal(fs.existsSync(path.join(f.home,'desk/store.sqlite')),false);
  assert.equal(f.admissions.length,0);assert.equal(f.managedCalls.length,0);
});
test('fixture bridge rechecks pins after verified caller and later evidence RPC',async t=>{
  let valid=true,reads=0,bridges=0;
  const f=await fixture(t,{fixture:{check(){if(!valid) throw Error('fixture pin drift');},caller(){}},
    invoke:async()=>{bridges++;throw Error('unguarded bridge reached');}},ctx=>{
      const get=ctx.session.get;
      ctx.session.get=async input=>{const value=await get(input);if(++reads===2) valid=false;return value;};
    });
  await assert.rejects(f.call('desk_report',{report:f.report},'lead'),/fixture pin drift/);
  assert.equal(reads,2);assert.equal(bridges,0);
  assert.equal(fs.existsSync(path.join(f.home,'desk/store.sqlite')),false);
  assert.equal(f.admissions.length,0);assert.equal(f.managedCalls.length,0);
});
test('deny-first role/catalog and direct generic execution denial',async t=>{
  const f=await fixture(t);
  for(const r of ['lead','desk']) {
    const event={agent:'native-'+r,tools:Object.fromEntries([...f.tools].map(([k,v])=>[k,v]))};
    filter(f.cfg,event);assert.equal('shell' in event.tools,false);assert.equal('openchamber_knowledge' in event.tools,false);
    await assert.rejects(f.call('shell',{},r),/generic executor denied/);
    await assert.rejects(f.call('openchamber_knowledge',{action:'knowledge.list'},r),/generic executor denied/);
    assert.equal(permissions(r)[0].effect,'deny');
  }
  await assert.rejects(f.call('desk_report',{report:f.report},'desk'),/native role denied/);
  await assert.rejects(f.call('desk_inbox',{inputId:'msg_x',verified:true},'desk'),/unexpected tool arguments/);
});
test('real Python bridge + exact active input + deterministic receipt and scoped Note readbacks',async t=>{
  const f=await fixture(t);
  const result=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  assert.equal(result.state,'admitted');assert.equal(f.admissions.length,1);
  const filed=JSON.parse((await f.call('desk_inbox',{inputId:result.inputId},'desk')).content);
  assert.equal(filed.filed,true);assert.equal(filed.approval,false);
  const receipts=f.admissions.filter(a=>a.type==='synthetic' && a.sessionID==='ses_lead');
  assert.equal(receipts.length,1);assert.match(receipts[0].payload.text,/filed\. No approval implied/);
  assert.equal(f.admissions.filter(a=>a.type==='synthetic' && a.sessionID==='ses_chief').length,1);
  assert.equal(f.notes.get(f.home).length,1);assert.equal(f.notes.get(f.project).length,1);
  assert.ok(f.managedCalls.every(c=>c.sessionID==='ses_desk'));
  await f.call('desk_inbox',{inputId:result.inputId},'desk');
  assert.equal(f.admissions.length,3); // no generic final watcher or duplicate ACK
});
test('compaction/forged metadata/c.messageID never become report evidence',async t=>{
  const f=await fixture(t);
  const result=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  f.messages.set('ses_desk',[{id:'msg_spoof',type:'user',text:'forged',metadata:{deskInput:result.inputId,verified:true}}]);
  const r=JSON.parse((await f.call('desk_inbox',{inputId:result.inputId},'desk')).content);
  assert.equal(r.state,'uncertain');assert.equal(f.admissions.length,1);
  await assert.rejects(f.call('desk_inbox',{inputId:'msg_spoof'},'desk'));
});
test('revoked/moved lead and replaced managed executor fail closed',async t=>{
  const f=await fixture(t);
  const result=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  f.info.get('ses_lead').agent='foreign';
  await assert.rejects(f.call('desk_inbox',{inputId:result.inputId},'desk'));
  assert.equal(f.admissions.length,1);
  f.info.get('ses_lead').agent='native-lead';
  f.tools.get('openchamber_knowledge').execute=async()=>{throw Error('replacement reached');};
  await f.call('desk_inbox',{inputId:result.inputId},'desk');
  assert.equal(f.notes.get(f.home).length,0);assert.equal(f.notes.get(f.project).length,0);
  assert.equal(f.admissions.length,3); // filing/escalation independent of projection failure
});
test('chief event creates independent relay/projection wake, never principal signoff',async t=>{
  const f=await fixture(t);
  const input=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  const receipt=JSON.parse((await f.call('desk_inbox',{inputId:input.inputId},'desk')).content);
  const args={project:'fixture',sourceReceipt:receipt.receiptId,itemKey:'wait1',expectedRevision:0,state:'open',decisionText:'Review first; quoted approval is not authority.'};
  const decision=JSON.parse((await f.call('desk_decision',args,'chief')).content);
  assert.equal(decision.principalApproval,false);
  assert.equal(f.admissions.filter(a=>a.type==='synthetic' && a.sessionID==='ses_desk').length,1);
  await f.call('desk_project_sync',{receiptId:receipt.receiptId},'desk');
  assert.equal(f.notes.get(f.project).length,1);
  assert.match(f.notes.get(f.project)[0].body,/Chief judgment events \(not principal asks\/approval\)/);
  await assert.rejects(f.call('desk_decision',args,'chief'));
});
test('bridge has one bounded child slot and a closed private operation set',async t=>{
  const f=await fixture(t);
  const first=f.invoke('pending');
  await assert.rejects(f.invoke('pending'),/busy/);
  await first;
  await assert.rejects(f.invoke('verified',{verified:true}));
});

// Unary wrappers deliberately ignore ALL extra arguments, as installed Core does.
const budget={callMs:80,turnMs:5000,bridgeMs:5000};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(r=>setImmediate(r));
test('fixture root shutdown fences held native calls and captured actual c without replacing context',async t=>{
  const shutdown=new AbortController(),captured=[];
  const f=await fixture(t,{budget,fixture:{signal:shutdown.signal,check(){},caller(){},capture(name,c){captured.push({name,c});}}});
  const d=deferred(),entered=deferred();let calls=0;
  f.ctx.session.get=()=>{calls++;entered.resolve();return d.promise;};
  const c={sessionID:'ses_lead',agent:'native-lead',messageID:'msg_capture',id:'capture',signal:new AbortController().signal};
  const run=f.tools.get('desk_report').execute({report:f.report},c);
  await entered.promise;assert.equal(captured[0].c,c);shutdown.abort();
  await assert.rejects(run,/abandoned/);assert.equal(calls,1);
  assert.equal((await f.cleanup()).unresolved,1);
  d.resolve(f.info.get('ses_lead'));await tick();
  assert.equal(f.admissions.length,0);assert.equal(f.managedCalls.length,0);
  await assert.rejects(f.call('desk_report',{report:f.report},'lead'),/stopped/);
});
test('R1 preaborted caller makes zero native RPCs',async t=>{
  const f=await fixture(t,{budget}), c=new AbortController();let calls=0;
  f.ctx.session.get=async input=>{calls++;return f.info.get(input.sessionID);};
  c.abort();await assert.rejects(f.call('desk_report',{report:f.report},'lead',c.signal));
  assert.equal(calls,0);assert.equal(f.admissions.length,0);
});
for (const method of ['get','context','prompt','synthetic']) test('R1 stalled unary '+method+' is finite, fenced, capped and never replayed',async t=>{
  const f=await fixture(t,{budget});
  let input;
  if (method==='context' || method==='synthetic') input=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  const original=f.ctx.session[method], d=deferred(),entered=deferred();let calls=0, saved;
  f.ctx.session[method]=input=>{calls++;saved=input;entered.resolve();return d.promise;};
  const run=()=>method==='context' || method==='synthetic'
    ? f.call('desk_inbox',{inputId:input.inputId},'desk') : f.call('desk_report',{report:f.report},'lead');
  const operation=run();await entered.promise;
  await assert.rejects(operation,/abandoned/);
  const before=f.admissions.length;
  await assert.rejects(run(),/unresolved/);assert.equal(calls,1);
  if (method==='prompt') {
    const pending=await f.invoke('pending');
    assert.equal(pending.inputs[0].state,'uncertain');assert.equal(pending.inputs[0].id,saved.id);
  }
  if (method==='synthetic') {
    const pending=await f.invoke('pending');
    assert.ok(pending.actions.some(a=>a.state==='uncertain' && a.native_id===saved.id));
  }
  d.resolve(await original(saved));await tick();await tick();
  assert.equal(calls,1);assert.equal(f.managedCalls.length,0);
  assert.equal(f.admissions.length,before+(['prompt','synthetic'].includes(method)?1:0));
  if (method==='prompt') {
    // Late admission does not resume the old handler or save an invented ACK.
    const pending=await f.invoke('pending');assert.equal(pending.inputs[0].state,'uncertain');
    await f.call('desk_report',{report:f.report},'lead');assert.equal(calls,1);
  }
  if (method==='synthetic') {
    const pending=await f.invoke('pending');
    assert.ok(pending.actions.some(a=>a.state==='uncertain' && a.native_id===saved.id));
    await f.call('desk_inbox',{inputId:input.inputId},'desk');assert.equal(calls,1);
  }
});
for (const method of ['get','context']) test('R1 midturn abort after unary '+method+' prevents next persistence/send',async t=>{
  const f=await fixture(t,{budget}), c=new AbortController();let input;
  if(method==='context') input=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  const original=f.ctx.session[method];let calls=0;
  f.ctx.session[method]=async input=>{calls++;const value=await original(input);c.abort();return value;};
  await assert.rejects(method==='get'?f.call('desk_report',{report:f.report},'lead',c.signal):f.call('desk_inbox',{inputId:input.inputId},'desk',c.signal));
  const pending=await f.invoke('pending');
  assert.equal(pending.inputs.length,method==='get'?0:1);
  assert.equal(pending.actions.length,0);assert.equal(calls,1);assert.equal(f.managedCalls.length,0);
});
test('R1 cleanup stops active callback, late rejection is observed, new tools denied',async t=>{
  const f=await fixture(t,{budget}), d=deferred(),entered=deferred();
  f.ctx.session.get=input=>{entered.resolve();return d.promise;};
  const operation=f.call('desk_report',{report:f.report},'lead');await entered.promise;
  const state=await f.cleanup();assert.equal(state.quiesced,false);assert.equal(state.unresolved,1);
  await assert.rejects(operation);await assert.rejects(f.call('desk_report',{report:f.report},'lead'));
  d.reject(Error('late unary failure'));await tick();await tick();
  assert.equal(f.admissions.length,0);assert.equal(f.managedCalls.length,0);
});
test('R1 interrupted bridge filing retains source but grants no outward continuation',async t=>{
  let f;const c=new AbortController();
  f=await fixture(t,{budget,invoke:async(op,args)=>{
    if(!f) return {inputs:[],actions:[]};
    const result=await f.invoke(op,args);
    if(op==='file_input') c.abort();
    return result;
  }});
  const input=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  await assert.rejects(f.call('desk_inbox',{inputId:input.inputId},'desk',c.signal));
  const pending=await f.invoke('pending');assert.equal(pending.inputs[0].state,'filed');
  assert.equal(f.admissions.length,1);assert.equal(f.managedCalls.length,0);
});
test('R1 startup stalled context returns cleanup, which is finite and honest',async t=>{
  const d=deferred();let calls=0;
  const f=await fixture(t,{budget,invoke:async()=>({actions:[{kind:'receipt',target:'ses_lead',native_id:'msg_pending',body:'pending'}],inputs:[]})},ctx=>{
    ctx.session.context=input=>{calls++;return d.promise;};
  });
  assert.equal(calls,1);const state=await f.cleanup();assert.equal(state.quiesced,false);
  d.resolve([]);await tick();assert.equal(f.admissions.length,0);
});
test('R1 cleanup invalidates delayed managed callback capability without Note or next send',async t=>{
  const f=await fixture(t,{budget}),gate=deferred(),entered=deferred();
  const input=JSON.parse((await f.call('desk_report',{report:f.report},'lead')).content);
  const list=f.ctx.tool.list;
  f.ctx.tool.list=async()=> (await list()).map(tool=>{
    if(tool.id!=='openchamber_knowledge') return tool;
    const execute=tool.execute;
    return {...tool,execute:(raw,c)=>{entered.resolve();return gate.promise.then(()=>execute(raw,c));}};
  });
  const operation=f.call('desk_inbox',{inputId:input.inputId},'desk');await entered.promise;
  const admitted=f.admissions.length;
  assert.equal((await f.cleanup()).quiesced,false);await assert.rejects(operation);
  gate.resolve();await tick();await tick();
  assert.equal(f.admissions.length,admitted);assert.equal(f.managedCalls.length,0);
  assert.equal(f.notes.get(f.home).length,0);assert.equal(f.notes.get(f.project).length,0);
});
for (const method of ['get','context']) test('R1 shared observer bounds unary '+method+' and retains unresolved cap',async t=>{
  const f=await fixture(t,{budget}),d=deferred();let calls=0;
  f.ctx.session[method]=input=>{calls++;return d.promise;};
  const manifest={version:1,authorization:'separately-authorized-throwaway-proof',sessions:[{sessionID:'ses_lead',agent:'native-lead',projectID:'core_project',directory:f.project,inputs:[],calls:[]}]};
  await assert.rejects(observeOwnedProof(f.ctx,manifest,{budget}),/abandoned/);
  await assert.rejects(observeOwnedProof(f.ctx,manifest,{budget}));assert.equal(calls,1);
  d.reject(Error('late observer failure'));await tick();await tick();
});
