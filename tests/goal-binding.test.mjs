// Contract fixtures only: no listener, real HTTP, native app, model or goal wakeup.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {boundGoalRequest,loadBinding,privatePath,validateOrigin,validateAuth} from '../hosts/domain-policy/goal-binding.mjs';
import {leadStartTool} from '../hosts/domain-policy/lead-start.mjs';
import {bindGoal} from '../scripts/bind-goal.mjs';

function fixture(t) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'goal-fixture-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const home=path.join(root,'home'),outcome=path.join(home,'outcomes','study'),host=path.join(root,'host');
  fs.mkdirSync(outcome,{recursive:true});fs.mkdirSync(host,{mode:0o700});
  const config={home,chief_agent:'example-chief',lead_agent:'example-lead',worker_agent:'example-worker',goal_binding:path.join(host,'binding.json')};
  const server={pid:1234,startedAt:'2026-10-16T00:00:00.000Z',runtime:'desktop',openchamberVersion:'fixture',port:12345};
  const binding={version:1,home,lead_agent:config.lead_agent,origin:'http://127.0.0.1:12345',auth:{Authorization:'Bearer FIXTURE_ONLY_SECRET'},server};
  const save=()=>fs.writeFileSync(config.goal_binding,JSON.stringify(binding),{mode:0o600});save();
  const sessions=new Map();
  const session=(id,agent,directory)=>({id,agent,location:{directory},time:{created:123},model:{providerID:'fixture',id:'only'}});
  sessions.set('ses_chief',session('ses_chief',config.chief_agent,home));
  const calls=[];let next=0;
  const f={root,home,outcome,host,config,server,binding,save,sessions,calls,
    resultPatch:{},goal:{id:'fixture-goal',status:'active'},httpOK:true,createdModel:{providerID:'fixture',id:'only'}};
  f.ctx={session:{get:async ({sessionID})=>sessions.get(sessionID)}};
  f.fetch=async (url,options)=>{
    calls.push({url,options});assert.equal(options.redirect,'error');
    assert.ok(url.startsWith(binding.origin+'/api/'));
    for (const [key,value] of Object.entries(binding.auth)) assert.equal(options.headers[key],value);
    const route=new URL(url).pathname;let result;
    if (route==='/api/system/info') result=f.info??server;
    else if (route.startsWith('/api/session/')) {
      const value=sessions.get(route.split('/').at(-1));result={data:f.remote??value};
    } else if (route.endsWith('/metadata')) result={metadata:{openchamber:{goal:f.goal}}};
    else if (route==='/api/openchamber/control') {
      if (f.throwPost) throw Error('secret response '+binding.auth.Authorization);
      const {action,input}=JSON.parse(options.body);assert.equal(action,'session.create');
      assert.deepEqual(Object.keys(input).sort(),['agent','directory','goal','lastAssistant','model','prompt','title','wait']);
      assert.equal(input.goal,true);assert.equal(input.agent,config.lead_agent);
      assert.ok(!options.body.includes('FIXTURE_ONLY_SECRET'));
      // Simulate the source-proven empty/unknown catalog path allowing Auto to
      // resolve a category's agent before dispatch. No actual router is executed.
      const autoOverride=f.emptyModelCatalog && input.model==='openchamber/auto';
      const agent=autoOverride ? 'build' : f.createdAgent??config.lead_agent;
      const id='ses_lead'+(++next);sessions.set(id,{...session(id,agent,input.directory),model:f.createdModel});
      // Exact CLI/control public success envelope, model is an object (not input string).
      result={sessionId:id,directory:input.directory,title:input.title,model:{providerID:'fixture',modelID:'only'},
        agent:autoOverride ? 'build' : config.lead_agent,promptDispatched:true,dispatchedAsCommand:false,goalEnabled:true,...f.resultPatch};
    } else throw Error('unknown route');
    return {ok:route!=='/api/openchamber/control'||f.httpOK,json:async()=>result};
  };
  f.request=()=>boundGoalRequest(f.ctx,config,{fetchImpl:f.fetch});
  f.tool=()=>leadStartTool(f.ctx,config,f.request());
  f.input={directory:outcome,objective:'Synthetic fixture objective; read LEAD.md and continue.',model:'fixture/only'};
  f.chief={agent:config.chief_agent,sessionID:'ses_chief'};
  f.posts=()=>calls.filter(c=>c.options.method==='POST');
  return f;
}
test('fixture: real CLI envelope decoded; persisted goal and native lead independently confirmed',async t=>{
  const f=fixture(t),result=JSON.parse((await f.tool().execute(f.input,f.chief)).content);
  assert.equal(result.sessionId,'ses_lead1');assert.equal(result.goalEnabled,true);
  assert.equal(f.posts().length,1);assert.equal(f.calls.length,4);
  assert.equal(JSON.stringify(result).includes('FIXTURE_ONLY_SECRET'),false);
  await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,1);
});
test('fixture: fresh lead uses SAME goal bridge with explicit authority, never a2a goal',async t=>{
  const f=fixture(t);await f.tool().execute(f.input,f.chief);
  const c={agent:f.config.lead_agent,sessionID:'ses_lead1'};
  await assert.rejects(()=>f.tool().execute(f.input,c));
  const result=JSON.parse((await f.tool().execute({...f.input,replacement:true},c)).content);
  assert.equal(result.sessionId,'ses_lead2');assert.equal(f.posts().length,2);
  await assert.rejects(()=>f.tool().execute({...f.input,replacement:true},c));
  assert.equal(f.posts().length,2);
});
for (const patch of [{goalEnabled:false},{goalEnabled:'true'},{promptDispatched:false},{promptError:'private response'},
  {partial:true},{error:'private error'},{dispatchedAsCommand:true},{sessionId:'bad'},{sessionId:'ses_chief'},
  {directory:'/elsewhere'},{agent:'build'},{model:{providerID:'wrong',modelID:'only'}}]) {
  test('fixture: partial/ignored fields block success and durable replay '+JSON.stringify(Object.keys(patch)),async t=>{
    const f=fixture(t);f.resultPatch=patch;
    await assert.rejects(()=>f.tool().execute(f.input,f.chief),/uncertain.*DO NOT replay/);
    await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,1);
    assert.ok(fs.readdirSync(f.host).some(p=>p.endsWith('.lock')));
  });
}
for (const scenario of ['http-error','network','goal-missing','goal-paused','wrong-native-agent']) {
  test('fixture: '+scenario+' is uncertain, sanitized, and never retried',async t=>{
    const f=fixture(t);
    if (scenario==='http-error') {f.httpOK=false;f.resultPatch={partial:true,partialAction:'goal-configured',error:'private error'};}
    if (scenario==='network') f.throwPost=true;
    if (scenario==='goal-missing') f.goal=undefined;
    if (scenario==='goal-paused') f.goal={id:'fixture',status:'paused'};
    if (scenario==='wrong-native-agent') f.createdAgent='build';
    await assert.rejects(()=>f.tool().execute(f.input,f.chief),e=>/uncertain/.test(e.message)&&!e.message.includes('SECRET'));
    await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,1);
  });
}
test('fixture: pin mismatch, unauthenticated info, native caller mismatch make no POST',async t=>{
  for (const info of [{pid:999},{startedAt:'2026-10-17T00:00:00Z'},{runtime:'web'},{port:undefined}]) {
    const f=fixture(t);f.info={...f.server,...info};
    await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,0);
  }
  const f=fixture(t);f.remote={...f.sessions.get('ses_chief'),agent:'build'};
  await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,0);
});
test('fixture: untrusted, unreadable, absent, linked and wrong-scope binding never contacts network',async t=>{
  for (const kind of ['absent','public','unreadable','linked','scope','endpoint','auth','parent']) {
    const f=fixture(t);
    if (kind==='absent') fs.unlinkSync(f.config.goal_binding);
    if (kind==='public') fs.chmodSync(f.config.goal_binding,0o644);
    if (kind==='unreadable') fs.chmodSync(f.config.goal_binding,0);
    if (kind==='linked') {fs.renameSync(f.config.goal_binding,f.config.goal_binding+'.real');fs.symlinkSync(f.config.goal_binding+'.real',f.config.goal_binding);}
    if (kind==='scope') {f.binding.home='/foreign';f.save();}
    if (kind==='endpoint') {f.binding.origin='http://example.com:12345';f.save();}
    if (kind==='auth') {f.binding.auth={Authorization:'Bearer x\r\nX: y'};f.save();}
    if (kind==='parent') fs.chmodSync(f.host,0o777);
    await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.calls.length,0);
  }
});
test('fixture: worker, impostor, foreign root, links, extra auth/action keys cannot create',async t=>{
  const f=fixture(t);
  for (const c of [{agent:f.config.worker_agent,sessionID:'ses_chief'},{agent:f.config.chief_agent,sessionID:'ses_missing'}]) {
    await assert.rejects(()=>f.tool().execute(f.input,c));
  }
  for (const input of [{directory:f.home},{directory:f.root},{endpoint:'http://127.0.0.1:1'},{authorization:'secret'},
    {agent:'build'},{action:'session.send'},{replacement:true},{model:'fixture/only\nunsafe'}]) {
    await assert.rejects(()=>f.tool().execute({...f.input,...input},f.chief));
  }
  const link=path.join(f.home,'outcomes','linked');fs.symlinkSync(f.outcome,link);
  await assert.rejects(()=>f.tool().execute({...f.input,directory:link},f.chief));
  assert.equal(f.calls.length,0);
});
test('fixture: only literal authenticated loopback and established auth headers accepted',()=>{
  for (const origin of ['https://127.0.0.1:12345','http://localhost:12345','http://127.0.0.1:12345/path','http://127.0.0.1:12345?x=1','http://user:pass@127.0.0.1:12345','http://example.com:12345']) assert.throws(()=>validateOrigin(origin));
  assert.deepEqual(validateAuth({Cookie:'oc_ui_session_12345=fixture.cookie'}),{Cookie:'oc_ui_session_12345=fixture.cookie'});
  for (const auth of [{},{Authorization:'Basic x'},{Authorization:'Bearer x',extra:'x'},{Cookie:'arbitrary=x'}]) assert.throws(()=>validateAuth(auth));
});
test('fixture: operator setup uses only authenticated GET and refuses overwrite; no secret output',async t=>{
  const f=fixture(t);fs.unlinkSync(f.config.goal_binding);
  const auth=path.join(f.host,'auth.json');fs.writeFileSync(auth,JSON.stringify(f.binding.auth),{mode:0o600});
  const options={home:f.home,'lead-agent':f.config.lead_agent,binding:f.config.goal_binding,origin:f.binding.origin,'auth-file':auth};
  const output=await bindGoal(options,{fetchImpl:f.fetch});assert.ok(!output.includes('SECRET'));
  assert.equal(loadBinding(f.config).server.pid,1234);privatePath(f.config.goal_binding);
  await assert.rejects(()=>bindGoal(options,{fetchImpl:f.fetch}));assert.equal(f.posts().length,0);
});
test('fixture: explicit desktop settings use official port/token contract without modifying source',async t=>{
  const f=fixture(t);fs.unlinkSync(f.config.goal_binding);
  const source=path.join(f.host,'settings.json');
  const text=JSON.stringify({desktopLocalPort:12345,desktopLocalClientToken:'FIXTURE_ONLY_SECRET',unrelated:'preserved'});
  fs.writeFileSync(source,text,{mode:0o600});
  const options={home:f.home,'lead-agent':f.config.lead_agent,binding:f.config.goal_binding,origin:f.binding.origin,'desktop-settings':source};
  await bindGoal(options,{fetchImpl:f.fetch});assert.equal(fs.readFileSync(source,'utf8'),text);
  fs.unlinkSync(f.config.goal_binding);fs.writeFileSync(source,JSON.stringify({desktopLocalPort:54321,desktopLocalClientToken:'FIXTURE_ONLY_SECRET'}));
  const count=f.calls.length;await assert.rejects(()=>bindGoal(options,{fetchImpl:f.fetch}));assert.equal(f.calls.length,count);
});
test('fixture: concurrent creates issue at most ONE POST',async t=>{
  const f=fixture(t),results=await Promise.allSettled([f.tool().execute(f.input,f.chief),f.tool().execute(f.input,f.chief)]);
  assert.equal(results.filter(x=>x.status==='fulfilled').length,1);assert.equal(f.posts().length,1);
});
test('fixture: replacement rejects another outcome, inactive goal, and unrecorded lead',async t=>{
  const f=fixture(t);await f.tool().execute(f.input,f.chief);
  const c={agent:f.config.lead_agent,sessionID:'ses_lead1'};
  const other=path.join(f.home,'outcomes','other');fs.mkdirSync(other);
  const before=f.posts().length;
  await assert.rejects(()=>f.tool().execute({...f.input,directory:other,replacement:true},c));
  f.goal={id:'fixture-goal',status:'paused'};
  await assert.rejects(()=>f.tool().execute({...f.input,replacement:true},c));
  f.goal={id:'fixture-goal',status:'active'};
  f.sessions.set('ses_unrecorded',{...f.sessions.get('ses_lead1'),id:'ses_unrecorded'});
  await assert.rejects(()=>f.tool().execute({...f.input,replacement:true},{...c,sessionID:'ses_unrecorded'}));
  assert.equal(f.posts().length,before);
});
test('fixture: existing official web UI cookie is usable without login or cookie refresh',async t=>{
  const f=fixture(t);f.binding.auth={Cookie:'oc_ui_session_12345=fixture.signed.cookie'};f.save();
  await f.tool().execute(f.input,f.chief);assert.equal(f.posts().length,1);
  assert.ok(f.calls.every(x=>x.options.headers.Cookie===f.binding.auth.Cookie));
});
test('R1 fixture: Auto with an empty model catalog is rejected before default bound requester/network/create',async t=>{
  const f=fixture(t);f.emptyModelCatalog=true;
  await assert.rejects(()=>f.tool().execute({...f.input,model:'openchamber/auto'},f.chief));
  assert.equal(f.posts().length,0);assert.equal(f.calls.length,0);
  assert.equal(f.sessions.size,1);assert.deepEqual(fs.readdirSync(f.host),['binding.json']);
});
test('R1 fixture: Auto cannot reach an operator-injected tool requester either',async t=>{
  const f=fixture(t);let requests=0;
  const tool=leadStartTool(f.ctx,f.config,async ()=>{requests++;throw Error('must not request');});
  await assert.rejects(()=>tool.execute({...f.input,model:'openchamber/auto'},f.chief));
  assert.equal(requests,0);
});
test('R1 fixture: direct binding boundary rejects Auto before network, even with empty model catalog',async t=>{
  const f=fixture(t);f.emptyModelCatalog=true;
  await assert.rejects(()=>f.request()({directory:f.outcome,agent:f.config.lead_agent,model:'openchamber/auto',goal:true,
    title:'[lead] study',prompt:'Goal: Fixture only',wait:false,lastAssistant:false},
    {sessionID:'ses_chief',replacement:false}));
  assert.equal(f.posts().length,0);assert.equal(f.calls.length,0);assert.equal(f.sessions.size,1);
});
for (const [name,model] of [['missing',undefined],['wrong-provider',{providerID:'wrong',id:'only'}],
  ['wrong-id',{providerID:'fixture',id:'wrong'}],['public-shape-not-native',{providerID:'fixture',modelID:'only'}]]) {
  test('R2 fixture: '+name+' native model leaves uncertain durable lock and no replay',async t=>{
    const f=fixture(t);f.createdModel=model;
    // Public result still reports the requested model, so only the independent
    // persisted native read can catch this mismatch/missing field.
    await assert.rejects(()=>f.tool().execute(f.input,f.chief),/uncertain.*DO NOT replay/);
    const locks=fs.readdirSync(f.host).filter(p=>p.endsWith('.lock'));
    assert.equal(locks.length,1);
    assert.equal(fs.readdirSync(f.host).filter(p=>p.endsWith('.json')).length,1); // binding only; no confirmed record
    const before=fs.readFileSync(path.join(f.host,locks[0]),'utf8');
    await assert.rejects(()=>f.tool().execute(f.input,f.chief));assert.equal(f.posts().length,1);
    assert.equal(fs.readFileSync(path.join(f.host,locks[0]),'utf8'),before);
  });
  test('R2 fixture: tool-level success independently rejects '+name+' native model',async t=>{
    const f=fixture(t);
    f.sessions.set('ses_injected',{id:'ses_injected',agent:f.config.lead_agent,location:{directory:f.outcome},model});
    const tool=leadStartTool(f.ctx,f.config,async ()=>({sessionId:'ses_injected',directory:f.outcome,goalEnabled:true,promptDispatched:true}));
    await assert.rejects(()=>tool.execute(f.input,f.chief),/identity.*mismatch.*reconcile/);
    assert.equal(f.calls.length,0);
  });
}
