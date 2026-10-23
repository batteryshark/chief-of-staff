import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {dispatchNative,validateDispatchRequest,nativeDispatchAdvice} from '../routing/host-dispatch.mjs';

const base=process.env.HOST_DISPATCH_TEST_ROOT ?? path.join(tmpdir(),'opencode');fs.mkdirSync(base,{recursive:true});
function fixture() {
  const directory=fs.mkdtempSync(path.join(base,'wiring-'));
  const c={sessionID:'ses_chief',messageID:'msg_call',id:'call_a',signal:new AbortController().signal};
  const model={providerID:'openai',id:'alias-fast',variant:'high'};
  const sessions=new Map([['ses_chief',{id:'ses_chief',agent:'chief-of-staff',location:{directory},time:{created:1}}]]);
  const histories=new Map([['ses_chief',[{id:'msg_call',type:'assistant',content:[{type:'tool',id:'call_a'}]}]]]);
  const a={id:'attempt_a',message_id:'msg_input_a',job:'dummy',state:'admitted',session_id:null,task:{directory},model:'openai/alias-fast',variant:'high'};
  const calls=[];let ledger=structuredClone(a);
  const options={workerAgent:'build',chiefPointerFile:path.join(directory,'chief.json'),holdBindings:{[directory]:[{file:path.join(directory,'holds.md'),heading:'## Dispatch',allowedQuote:'Allowed.'}]}};
  fs.writeFileSync(options.chiefPointerFile,JSON.stringify({session:'ses_chief',directory}));fs.writeFileSync(path.join(directory,'holds.md'),'## Dispatch\n\nAllowed.\n');
  const ctx={location:{directory},options:{hostDispatch:options},model:{list:async()=>[{...model,modelID:'underlying',enabled:true,variants:[{id:'high'}]}]},session:{
    get:async({sessionID})=>sessions.get(sessionID),context:async({sessionID})=>histories.get(sessionID),
    create:async body=>{calls.push(['create',body]);const worker={id:'ses_worker',...body,time:{created:1}};sessions.set(worker.id,worker);histories.set(worker.id,[]);return worker;},
    prompt:async body=>{calls.push(['prompt',body]);histories.get(body.sessionID).push({type:'user',id:body.id,text:body.text});return {id:body.id,sessionID:body.sessionID};},
    wait:async({sessionID},{signal})=>{calls.push(['wait',sessionID]);assert.ok(signal);histories.get(sessionID).push(
      {type:'assistant',id:'msg_answer_a',agent:'build',model,finish:'stop',time:{completed:1},content:[{type:'text',text:'ALPHA'}]},
      {type:'idle',id:'msg_idle_a',outcome:'succeeded'},
      {type:'user',id:'msg_newer_b',text:'BETA'},
      {type:'assistant',id:'msg_answer_b',agent:'build',model,finish:'stop',time:{completed:2},content:[{type:'text',text:'BETA'}]},
      {type:'idle',id:'msg_idle_b',outcome:'succeeded'});},
  }};
  const invoke=async request=>{
    calls.push([request.action]);
    if(request.action==='dispatch-get')return structuredClone(ledger);
    if(request.action==='dispatch-save'){
      assert.equal(ledger.host_dispatch?.state ?? null,request.expected_state);
      ledger.host_dispatch=structuredClone(request.value);ledger.session_id=request.value.sessionID ?? null;
      ledger.state=['admitted','collected'].includes(request.value.state)?'running':'uncertain';return structuredClone(ledger);
    }
    if(request.action==='dispatch-incomplete'){ledger.state='uncertain';ledger.host_dispatch.incomplete=true;return structuredClone(ledger);}
    throw Error('unexpected internal action');
  };
  const fetchImpl=async(url,request)=>{const body=JSON.parse(request.body);assert.equal(body.sessionID,c.sessionID);return {ok:true,json:async()=>({ok:true,data:{sessions:[...sessions.values()]}})};};
  return {ctx,c,model,sessions,histories,calls,invoke,fetchImpl,options,directory,get ledger(){return ledger;}};
}
async function run(f, request={action:'dispatch',attempt:'attempt_a',prompt:'ALPHA'}) {
  const before={fetch:globalThis.fetch,url:process.env.OPENCHAMBER_AGENT_TOOL_URL,token:process.env.OPENCHAMBER_AGENT_TOOL_TOKEN};
  globalThis.fetch=f.fetchImpl;process.env.OPENCHAMBER_AGENT_TOOL_URL='http://127.0.0.1:12345/api/openchamber/agent-tool';process.env.OPENCHAMBER_AGENT_TOOL_TOKEN='fixture-only';
  try{return await dispatchNative(f.ctx,f.c,request,f.invoke);}finally{
    globalThis.fetch=before.fetch;
    for(const [key,value] of [['OPENCHAMBER_AGENT_TOOL_URL',before.url],['OPENCHAMBER_AGENT_TOOL_TOKEN',before.token]])if(value===undefined)delete process.env[key];else process.env[key]=value;
  }
}
test('actual context to CAS to exact native create/wait/result; newer B cannot replace A',async()=>{
  const f=fixture(),result=await run(f);assert.equal(result.status,'collected');assert.equal(result.result.text,'ALPHA');assert.equal(result.result.assistantID,'msg_answer_a');
  assert.deepEqual(result.result.origin,{sessionID:f.c.sessionID,messageID:f.c.messageID,callID:f.c.id,directory:f.directory});
  assert.deepEqual(f.calls.find(c=>c[0]==='create')[1].model,f.model);assert.equal(f.calls.find(c=>c[0]==='create')[1].agent,'build');
  assert.equal(f.calls.filter(c=>c[0]==='wait').length,1);assert.equal(f.calls.filter(c=>c[0]==='prompt').length,1);
  assert.ok(f.calls.findIndex(c=>c[0]==='dispatch-save')<f.calls.findIndex(c=>c[0]==='create'));
});
test('agent JSON cannot supply origin, selection or internal CAS actions',()=>{
  for(const key of ['origin','model','agent','hostDispatch','value'])assert.throws(()=>validateDispatchRequest({action:'dispatch',attempt:'a',prompt:'dummy',[key]:'forged'}));
  assert.throws(()=>validateDispatchRequest({action:'dispatch-save',attempt:'a'}));
});
test('bound fresh prepare directs native path; absent policy/read/continuation output remains unchanged',()=>{
  const result={dispatch_allowed:true,action:'session.create',args:{returnResult:true},attempt:{id:'a'}};
  const routed=nativeDispatchAdvice({action:'prepare'},result,{});assert.equal(routed.action,'runway.dispatch');assert.deepEqual(routed.args,{attempt:'a'});
  assert.equal(nativeDispatchAdvice({action:'prepare'},result,undefined),result);
  assert.equal(nativeDispatchAdvice({action:'plan'},result,{}),result);
  const continuation={...result,action:'session.send'};assert.equal(nativeDispatchAdvice({action:'prepare'},continuation,{}),continuation);
});
test('absent policy disables dispatch only, before ledger/native side effects',async()=>{
  const f=fixture();f.ctx.options={};await assert.rejects(run(f),/disabled/);assert.equal(f.calls.length,0);
});
test('invalid completion bound refuses before admission or native effects',async()=>{
  const f=fixture();f.options.completionTimeoutMs=0;await assert.rejects(run(f),/Bounded/);assert.equal(f.calls.length,0);
});
test('native creation lost response leaves creating uncertainty and prevents a second create',async()=>{
  const f=fixture();f.ctx.session.create=async()=>{throw Error('lost ack');};await assert.rejects(run(f));assert.equal(f.ledger.state,'uncertain');assert.equal(f.ledger.host_dispatch.state,'creating');
  await assert.rejects(run(f),/Fresh unbound/);
});
test('timeout is incomplete; explicit original-owner collect never resends',async()=>{
  const f=fixture(),complete=f.ctx.session.wait;f.ctx.session.wait=async()=>{throw Error('timeout');};
  const pending=await run(f);assert.equal(pending.status,'incomplete');assert.equal(f.ledger.state,'uncertain');assert.equal(f.ledger.host_dispatch.state,'admitted');
  f.ctx.session.wait=complete;f.c.messageID='msg_retrieve';f.c.id='call_retrieve';
  const result=await run(f,{action:'collect-dispatch',attempt:'attempt_a'});
  assert.equal(result.status,'collected');assert.equal(result.result.origin.callID,'call_a');assert.equal(result.retrievedBy.callID,'call_retrieve');
  assert.equal(f.calls.filter(c=>c[0]==='prompt').length,1);
});
test('hold changed during native completion suppresses result and preserves uncertainty',async()=>{
  const f=fixture(),complete=f.ctx.session.wait;
  f.ctx.session.wait=async(...args)=>{await complete(...args);fs.writeFileSync(path.join(f.directory,'holds.md'),'## Dispatch\n\nHeld.\n');};
  const result=await run(f);assert.equal(result.status,'incomplete');assert.equal(result.result,undefined);assert.equal(f.ledger.state,'uncertain');
});
test('plugin routes dispatch with actual context and blocks internal agent actions before ordinary invoke',()=>{
  const source=fs.readFileSync(new URL('../routing/plugin.js',import.meta.url),'utf8');
  assert.match(source,/dispatchNative\(ctx,c,req,invoke\)/);assert.match(source,/req\.action\?\.startsWith\('dispatch-'\)/);
  assert.ok(source.indexOf('dispatchNative(ctx,c,req,invoke)')<source.indexOf('const result=nativeDispatchAdvice'));
});
