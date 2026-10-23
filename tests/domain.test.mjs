import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {leadStartTool,controlRequester} from '../hosts/domain-policy/lead-start.mjs';
import {validateDirectory,resolveOwner,prepareHandoff,receiveHandoff,deliveryOutcome} from '../services/directory/local.mjs';
import {makePlugin,filterCatalog,canEdit} from '../hosts/domain-policy/index.mjs';

// Explicit external source selection preserves the real descriptor/capture
// contract without assuming a private sibling checkout or vendoring transport.
// _tools builds descriptors only; no transport setup or live host is loaded.
const transportSource=process.env.CHIEF_A2A_TEST_MODULE;
if (!transportSource || !path.isAbsolute(transportSource))
  throw Error('Set CHIEF_A2A_TEST_MODULE to the approved absolute opencode-a2a src/plugin.js for development tests.');
const transportModule=pathToFileURL(transportSource).href;
const {_tools}=await import(transportModule);

function fixture(t) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'domain-fixture-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true})); // Only this test's own scratch.
  const tech=path.join(root,'technical'),home=path.join(root,'example'),outcome=path.join(home,'outcomes','study');
  fs.mkdirSync(tech);fs.mkdirSync(outcome,{recursive:true});
  const file=path.join(root,'domains.json');
  const row=(id,dir)=>({id,responsibility:id+' scope',server:'local',home:dir,pointer:path.join(dir,'chief.json')});
  const directory={version:1,domains:[row('technical',tech),row('example',home)]};
  fs.writeFileSync(file,JSON.stringify(directory));
  const pointer=(dir,session='ses_fixture')=>fs.writeFileSync(path.join(dir,'chief.json'),JSON.stringify({session,directory:dir,updated:new Date().toISOString()}));
  pointer(tech,'ses_tech');pointer(home,'ses_chief');
  const transport_module=transportModule;
  const config={id:'example',home,directory:file,chief_agent:'example-chief',lead_agent:'example-lead',worker_agent:'example-worker',
    managed_paths:[path.join(home,'AGENTS.md'),path.join(home,'managed-extra.md')],transport_module,
    transport_sha256:createHash('sha256').update(fs.readFileSync(fileURLToPath(transport_module))).digest('hex')};
  const envelope={version:1,id:'handoff-1',origin:{domain:'example',session:'ses_chief'},owner:'technical',action:'record-idea',principal_attribution:'synthetic fixture only',content:'Synthetic idea, not real principal content.'};
  return {root,tech,home,outcome,file,directory,pointer,config,envelope};
}

test('directory rereads live pointer on each preparation and rotation',t=>{
  const f=fixture(t);
  assert.equal(prepareHandoff(f.file,f.envelope).to,'local/ses_tech');
  f.pointer(f.tech,'ses_rotated');
  assert.equal(prepareHandoff(f.file,f.envelope).to,'local/ses_rotated');
  assert.equal(prepareHandoff(f.file,f.envelope).expectReply,true);
});
test('missing malformed future and wrong-home pointers fail closed',t=>{
  const f=fixture(t),p=path.join(f.tech,'chief.json');
  fs.unlinkSync(p);assert.throws(()=>resolveOwner(f.file,'technical'));
  for (const data of ['bad-json', JSON.stringify({session:'ses_x',directory:f.tech,updated:'bad'}),
    JSON.stringify({session:'ses_x',directory:f.tech,updated:'2100-01-01'}),
    JSON.stringify({session:'ses_x',directory:f.home,updated:new Date().toISOString()})]) {
    fs.writeFileSync(p,data);assert.throws(()=>resolveOwner(f.file,'technical'));
  }
  assert.throws(()=>resolveOwner(f.file,'unknown'),/clarify once/);
});
test('old rotation pointer resolves without refresh or heartbeat; age is diagnostic',t=>{
  const f=fixture(t),updated=new Date(Date.now()-48*3600000).toISOString();
  fs.writeFileSync(path.join(f.tech,'chief.json'),JSON.stringify({session:'ses_tech',directory:f.tech,updated}));
  assert.equal(resolveOwner(f.file,'technical').session,'ses_tech');
  assert.ok(resolveOwner(f.file,'technical').pointerAgeMs>=48*3600000);
});
test('directory rejects ambiguous owners homes remote aliases and malformed rows',t=>{
  const f=fixture(t);
  const duplicated=structuredClone(f.directory);duplicated.domains.push(duplicated.domains[0]);
  assert.throws(()=>validateDirectory(duplicated),/ambiguous/);
  for (const patch of [{server:'remote'},{pointer:'/other/chief.json'},{home:'relative'},{session:'ses_fixed'}]) {
    const d=structuredClone(f.directory);Object.assign(d.domains[0],patch);assert.throws(()=>validateDirectory(d));
  }
  assert.throws(()=>prepareHandoff(f.file,{...f.envelope,owner:'example'}),/self/);
});
test('technical receiver records once and returns automatic receipt without sending',t=>{
  const f=fixture(t);
  const first=receiveHandoff(f.file,'technical',f.tech,f.envelope);
  const ideas=fs.readFileSync(path.join(f.tech,'ideas.md'),'utf8');
  assert.equal(first.status,'recorded');
  assert.deepEqual(receiveHandoff(f.file,'technical',f.tech,{...f.envelope}),first);
  assert.equal(fs.readFileSync(path.join(f.tech,'ideas.md'),'utf8'),ideas);
  assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(f.tech,'handoffs.json')))).length,1);
  assert.throws(()=>receiveHandoff(f.file,'technical',f.tech,{...f.envelope,content:'changed'}),/different content/);
  assert.equal(fs.existsSync(path.join(f.home,'ideas.md')),false);
});
test('receipt recovery after missing receipt does not duplicate idea marker',t=>{
  const f=fixture(t);
  receiveHandoff(f.file,'technical',f.tech,f.envelope);
  const original=fs.readFileSync(path.join(f.tech,'ideas.md'),'utf8');
  fs.unlinkSync(path.join(f.tech,'handoffs.json'));
  receiveHandoff(f.file,'technical',f.tech,f.envelope);
  assert.equal(fs.readFileSync(path.join(f.tech,'ideas.md'),'utf8'),original);
});
test('receiver rejects other memory owners and linked private stores',t=>{
  const f=fixture(t);
  assert.throws(()=>receiveHandoff(f.file,'technical',f.home,f.envelope),/not this memory owner/);
  assert.throws(()=>receiveHandoff(f.file,'example',f.home,{...f.envelope,owner:'example'}),/technical owner/);
  fs.symlinkSync(path.join(f.home,'sentinel'),path.join(f.tech,'ideas.md'));
  assert.throws(()=>receiveHandoff(f.file,'technical',f.tech,f.envelope),/linked/);
  assert.equal(fs.existsSync(path.join(f.home,'sentinel')),false);
});
test('timeout ack and once-only clarification never request resend or outward effects',()=>{
  assert.deepEqual(deliveryOutcome({},'timeout'),{status:'unresolved',send:false});
  const once=deliveryOutcome({},'unknown-owner');
  assert.equal(once.status,'needs-clarification');assert.equal(once.send,false);
  assert.equal(deliveryOutcome(once,'unknown-owner').status,'blocked');
  assert.equal(deliveryOutcome(once,'receipt').send,false);
  assert.throws(()=>deliveryOutcome({},'retry'));
});
test('helpers do not use fetch services schedules or outbound callbacks',t=>{
  const f=fixture(t);let calls=0;
  const saved=globalThis.fetch;globalThis.fetch=()=>{calls++;throw Error('no outbound');};
  try {prepareHandoff(f.file,f.envelope);receiveHandoff(f.file,'technical',f.tech,f.envelope);deliveryOutcome({},'receipt');}
  finally {globalThis.fetch=saved;}
  assert.equal(calls,0);
});

async function harness(f) {
  const hooks={},permission={},tools=new Map(),calls=[];
  const sessions=new Map([
    ['ses_chief',{agent:'example-chief',location:{directory:f.home}}],
    ['ses_lead',{agent:'example-lead',location:{directory:f.outcome},model:{providerID:'fixture',id:'only'}}],
    ['ses_worker',{agent:'example-worker',location:{directory:f.outcome}}],
    ['ses_tech',{agent:'chief-of-staff',location:{directory:f.tech}}],
  ]);
  for (const definition of _tools(undefined)) tools.set(definition.name,{...definition,options:{codemode:false},execute:async (input,c)=>{calls.push({name:definition.name,input,c});return {content:'fixture'};}});
  let replay;
  const ctx={session:{hook:async (name,fn)=>{hooks[name]=fn;},get:async ({sessionID})=>{
    if(!sessions.has(sessionID))throw Error('unknown session');return sessions.get(sessionID);}},
    permission:{hook:async(name,fn)=>{permission[name]=fn;}},
    tool:{list:async()=>[...tools].map(([id,t])=>({id,...t,execute:(...a)=>t.execute(...a)})),transform:async fn=>{
      replay=()=>fn({add:t=>tools.set(t.name,t),remove:n=>tools.delete(n),get:n=>{
        const t=tools.get(n);return t&&{...t,execute:(...a)=>t.execute(...a)};}});replay();}}};
  await makePlugin(f.config).setup(ctx);
  const call=(name,input,agent='example-chief',sessionID='ses_chief')=>tools.get(name).execute(input,{agent,sessionID});
  return {hooks,permission,tools,calls,sessions,call,ctx,replay};
}
test('catalog fixture removes Code Mode shell session bypasses and inherited tools only for scoped roles',t=>{
  const f=fixture(t),base={read:{},write:{},patch:{},shell:{},execute:{},openchamber:{},subagent:{},a2a_send:{},a2a_create:{},domain_a2a_send:{},domain_a2a_create:{},rogue_plugin:{}};
  for(const agent of ['example-chief','example-lead','example-worker']) {
    const event={agent,tools:structuredClone(base)};filterCatalog(f.config,event);
    for(const name of ['execute','shell','openchamber','subagent','rogue_plugin'])assert.equal(event.tools[name],undefined);
    assert.equal(event.tools.a2a_send,undefined);assert.equal(event.tools.a2a_create,undefined);
    assert.ok(event.tools.domain_a2a_send);assert.ok(event.tools.read);
    assert.equal(!!event.tools.domain_a2a_create,agent!=='example-worker');
  }
  const normal={agent:'chief-of-staff',tools:structuredClone(base)};filterCatalog(f.config,normal);
  const unchanged={...base};delete unchanged.domain_a2a_send;delete unchanged.domain_a2a_create;
  assert.deepEqual(normal.tools,unchanged);
});
test('native hook fixture registers all model flows and denies foreign/role-crossing memory edits',async t=>{
  const f=fixture(t),h=await harness(f);
  assert.deepEqual(Object.keys(h.hooks).sort(),['compaction','context','generate']);
  for(const fn of Object.values(h.hooks)) {
    const event={agent:'example-chief',tools:{execute:{},shell:{},read:{}}};await fn(event);assert.deepEqual(Object.keys(event.tools),['read']);
  }
  const event={agent:'example-chief',sessionID:'ses_chief',action:'edit',resources:[path.join(f.tech,'ideas.md')],effect:'allow'};
  await h.permission.evaluate(event);assert.equal(event.effect,'deny');
  assert.equal(canEdit(f.config,'chief',f.home,'brief.md'),true);
  assert.equal(canEdit(f.config,'chief',f.home,'chief.json'),true);
  assert.equal(canEdit(f.config,'chief',f.home,'AGENTS.md'),false);
  assert.equal(canEdit(f.config,'chief',f.home,'managed-extra.md'),false);
  assert.equal(canEdit(f.config,'chief',f.home,'.opencode/plugins/malicious.js'),false);
  assert.equal(canEdit(f.config,'lead',f.outcome,'LEAD.md'),true);
  assert.equal(canEdit(f.config,'lead',f.outcome,path.join(f.home,'principal.md')),false);
  assert.equal(canEdit(f.config,'worker',f.outcome,'output/result.md'),true);
  fs.symlinkSync(f.tech,path.join(f.home,'linked'));
  assert.equal(canEdit(f.config,'chief',f.home,'linked/ideas.md'),false);
});
test('guarded a2a refuses arbitrary agent creation directory escapes and send-create bypass',async t=>{
  const f=fixture(t),h=await harness(f);
  await h.call('domain_a2a_create',{server:'local',agent:'example-lead',directory:f.outcome});
  assert.equal(h.calls.length,1);
  await assert.rejects(()=>h.call('domain_a2a_create',{server:'local',agent:'build',directory:f.outcome}));
  await assert.rejects(()=>h.call('domain_a2a_create',{server:'local',agent:'example-lead',directory:f.tech}));
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_lead',create:{agent:'build'}}));
  await assert.rejects(()=>h.call('domain_a2a_create',{server:'local',agent:'example-worker'},'example-worker','ses_worker'));
  assert.equal(h.calls.length,1);
  await h.call('domain_a2a_create',{server:'local',agent:'example-chief',directory:f.home,nest:false});
  await h.call('domain_a2a_create',{server:'local',agent:'example-worker'},'example-lead','ses_lead');
  assert.equal(h.calls.length,3);
  h.sessions.set('ses_fresh',{agent:'example-chief',location:{directory:f.home},metadata:{a2a:{createdBy:'self/ses_chief'}}});
  await h.call('domain_a2a_send',{to:'local/ses_fresh',text:'Read state, update your pointer, continue.'});
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_chief',text:'bypass lead'},'example-worker','ses_worker'));
  assert.equal(h.calls.length,4);
});
test('guarded handoffs require fresh directory attribution and automatic reply, defaults untouched',async t=>{
  const f=fixture(t),h=await harness(f);
  await h.call('domain_a2a_send',{to:'local/ses_tech',text:JSON.stringify(f.envelope),expectReply:true});
  assert.equal(h.calls.length,1);
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_tech',text:'unattributed'}));
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_tech',text:JSON.stringify(f.envelope),expectReply:false}));
  f.pointer(f.tech,'ses_rotated');
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_tech',text:JSON.stringify(f.envelope)}));
  await h.call('a2a_send',{to:'anything',create:{}},'chief-of-staff','ses_tech');
  assert.equal(h.calls.length,2); // Technical executor passthrough, no catalog policy widening.
});
test('bridge-wrapped references work; unexpected descriptor or missing transport fails capture',async t=>{
  const f=fixture(t),h=await harness(f);
  const event={agent:'example-chief',tools:{domain_a2a_send:{},domain_a2a_create:{},a2a_send:{},read:{}}};
  await h.hooks.context(event);assert.ok(event.tools.domain_a2a_send);assert.equal(event.tools.a2a_send,undefined);
  h.tools.get('a2a_send').description='unexpected replacement';
  h.tools.delete('a2a_create');
  await assert.rejects(()=>h.call('domain_a2a_send',{to:'local/ses_lead',text:'test'}),/unavailable\/replaced/);
  await assert.rejects(()=>h.call('domain_a2a_create',{server:'local',agent:'example-lead',directory:f.outcome}),/unavailable\/replaced/);
});
test('owner liveness checks reject archived missing wrong-agent and wrong-location sessions',async t=>{
  const f=fixture(t),h=await harness(f),input={to:'local/ses_tech',text:JSON.stringify(f.envelope)};
  for(const target of [{agent:'chief-of-staff',location:{directory:f.tech},time:{archived:1}},
    {agent:'build',location:{directory:f.tech}},{agent:'chief-of-staff',location:{directory:f.home}}]) {
    h.sessions.set('ses_tech',target);await assert.rejects(()=>h.call('domain_a2a_send',input));
  }
  h.sessions.delete('ses_tech');await assert.rejects(()=>h.call('domain_a2a_send',input));
  assert.equal(h.calls.length,0);
});
test('narrow goal bridge pins supported create action/agent/directory and requires confirmed goal',async t=>{
  const f=fixture(t),h=await harness(f);let sent;
  const request=controlRequester('http://127.0.0.1:12345/api/openchamber/control','Basic fixture',async (url,options)=>{
    assert.equal(options.redirect,'error');sent=JSON.parse(options.body);return {ok:true,json:async()=>({sessionId:'ses_lead',directory:f.outcome,goalEnabled:true,promptDispatched:true})};
  });
  const tool=leadStartTool(h.ctx,f.config,request),c={agent:'example-chief',sessionID:'ses_chief'};
  await tool.execute({directory:f.outcome,objective:'Synthetic outcome',model:'fixture/only'},c);
  assert.equal(sent.action,'session.create');assert.equal(sent.input.goal,true);assert.equal(sent.input.agent,'example-lead');
  await assert.rejects(()=>tool.execute({directory:f.tech,objective:'no',model:'fixture/only'},c));
  await assert.rejects(()=>tool.execute({directory:f.outcome,objective:'no',model:'fixture/only',action:'session.send'},c));
  await assert.rejects(()=>leadStartTool(h.ctx,f.config).execute({directory:f.outcome,objective:'no',model:'fixture/only'},c),/not configured/);
  assert.throws(()=>controlRequester('https://example.com/api/openchamber/control','token'));
});
test('generated-style plugin wires optional host loader without injection; disabled means no network',async t=>{
  const f=fixture(t);f.config.goal_binding=path.join(f.root,'operator-only','binding.json');
  const saved=globalThis.fetch;let calls=0;
  globalThis.fetch=()=>{calls++;throw Error('network forbidden');};
  try {
    const h=await harness(f);
    await assert.rejects(()=>h.call('domain_lead_start',{directory:f.outcome,objective:'Fixture only',model:'fixture/only'}),/binding\/identity\/authority unavailable/);
    for (const agent of ['example-chief','example-lead','example-worker']) {
      const event={agent,tools:{domain_lead_start:{},openchamber:{},shell:{},execute:{}}};
      filterCatalog(f.config,event);
      assert.equal(Boolean(event.tools.domain_lead_start),agent!=='example-worker');
      assert.equal(event.tools.openchamber,undefined);assert.equal(event.tools.shell,undefined);assert.equal(event.tools.execute,undefined);
    }
    assert.equal(calls,0);
  } finally {globalThis.fetch=saved;}
});
