import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {dispatchEligibility} from '../routing/dispatch-eligibility.mjs';

const base=process.env.HOST_DISPATCH_TEST_ROOT ?? path.join(tmpdir(),'opencode');fs.mkdirSync(base,{recursive:true});
function fixture() {
  const dir=fs.mkdtempSync(path.join(base,'eligibility-'));
  const origin={sessionID:'ses_chief',messageID:'msg_call',callID:'call_a',directory:dir};
  const sessions=new Map(['ses_chief','ses_lead','ses_worker','ses_other'].map(id=>[id,{id,agent:id==='ses_lead'?'lead':'build',location:{directory:dir},time:{created:1}}]));
  const options={chiefPointerFile:path.join(dir,'chief.json'),rosterFile:path.join(dir,'roster.jsonl'),holdBindings:{[dir]:[{file:path.join(dir,'holds.md'),heading:'## Dispatch',allowedQuote:'Explicitly allowed.'}]}};
  fs.writeFileSync(options.chiefPointerFile,JSON.stringify({session:'ses_chief',directory:dir}));
  fs.writeFileSync(options.rosterFile,JSON.stringify({session:'ses_lead',directory:dir,state:'active'})+'\n');
  fs.writeFileSync(path.join(dir,'holds.md'),'## Dispatch\n\nExplicitly allowed.\n');
  const ctx={location:{directory:dir},session:{get:async({sessionID})=>sessions.get(sessionID)}};
  const a={state:'running',task:{directory:dir},session_id:'ses_worker',host_dispatch:{origin,sessionID:'ses_worker',directory:dir,agent:'build'}};
  const env={OPENCHAMBER_AGENT_TOOL_URL:'http://127.0.0.1:12345/api/openchamber/agent-tool',OPENCHAMBER_AGENT_TOOL_TOKEN:'fixture-only'};
  const connection={env,fetchImpl:async(url,request)=>{
    const body=JSON.parse(request.body);assert.equal(body.input.action,'session.list');assert.equal(body.input.all,true);assert.equal(body.sessionID,origin.sessionID);
    return {ok:true,json:async()=>({ok:true,data:{sessions:[...sessions.values()]}})};
  }};
  const make=(o=origin,op=options)=>dispatchEligibility(ctx,op,async()=>a,o,{sessionID:o.sessionID,id:'actual_call'},connection);
  return {dir,origin,sessions,options,ctx,a,make,connection};
}
test('actual chief pointer, native identity, holds and archive overlay all required',async()=>{
  const f=fixture();const state=await f.make()(f.origin);assert.equal(state.held,false);assert.equal(state.archived,false);
});
test('unchanged enrolled lead gate reads real active roster',async()=>{
  const f=fixture(),o={...f.origin,sessionID:'ses_lead'};f.connection.fetchImpl=async()=>({ok:true,json:async()=>({ok:true,data:{sessions:[...f.sessions.values()]}})});
  await f.make(o)(o);fs.writeFileSync(f.options.rosterFile,JSON.stringify({session:'ses_lead',directory:f.dir,state:'hold'}));
  await assert.rejects(f.make(o)(o),/held\/archived\/ineligible/);
});
test('agent-name-only chief/unregistered repair lead never granted',async()=>{
  const f=fixture(),o={...f.origin,sessionID:'ses_other'};f.sessions.get('ses_other').agent='chief-of-staff';await assert.rejects(f.make(o)(o));
});
test('changed chief pointer and missing binding refuse',async()=>{
  const f=fixture();fs.writeFileSync(f.options.chiefPointerFile,JSON.stringify({session:'ses_other',directory:f.dir}));await assert.rejects(f.make()(f.origin));
  assert.throws(()=>f.make(f.origin,{}),/holds/);assert.throws(()=>f.make(f.origin,{...f.options,fixtureMode:true}),/production/);
});
test('app-only archive blocks even when native record is not archived',async()=>{
  const f=fixture();f.connection.fetchImpl=async()=>({ok:true,json:async()=>({ok:true,data:{sessions:[{...f.sessions.get('ses_chief'),time:{created:1,archived:2}}]}})});
  await assert.rejects(f.make()(f.origin),/App recipient archived/);
});
test('current hold section change blocks chief and its owned worker',async()=>{
  const f=fixture();fs.writeFileSync(path.join(f.dir,'holds.md'),'## Dispatch\n\nHeld.\n');await assert.rejects(f.make()({sessionID:'ses_worker',directory:f.dir}),/hold state/);
});
test('exact durable worker ownership required; native goal is refused',async()=>{
  const f=fixture(),w={sessionID:'ses_worker',directory:f.dir};await f.make()(w);
  f.a.host_dispatch.origin={...f.origin,callID:'wrong'};await assert.rejects(f.make()(w),/owned/);
  f.a.host_dispatch.origin=f.origin;f.sessions.get('ses_worker').metadata={openchamber:{goal:{status:'paused'}}};await assert.rejects(f.make()(w),/goal/);
});
test('unknown/truncated archive data and missing inherited auth fail closed',async()=>{
  const f=fixture();f.connection.fetchImpl=async()=>({ok:true,json:async()=>({ok:true,data:{sessions:[]}})});await assert.rejects(f.make()(f.origin),/absent/);
  f.connection.env.OPENCHAMBER_AGENT_TOOL_TOKEN='';await assert.rejects(f.make()(f.origin),/authentication/);
});
