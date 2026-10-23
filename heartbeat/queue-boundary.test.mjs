// Source fixtures only: stubbed host APIs are not native calls. No principal contacts.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Bus,unansweredEscalationMs} from './bus.mjs';
import {recipientEligibility,appSessionReader} from './records.mjs';
import {setupHeartbeat} from './plugin.mjs';
import {GoalWait} from './goal-wait.mjs';
import {ingestNodAnswer} from './nod.mjs';
import {checkKnown} from './nod-feed.mjs';

async function fixture(){
  const root=await mkdtemp(path.join(os.tmpdir(),'queue-boundary-'));
  let now=1000;const bus=new Bus(root,{now:()=>now});
  const origin={sessionID:'ses_lead',directory:'/fixture/lead'};
  const post=(key,urgency='normal',text=key)=>bus.post({key,ref:key,text,urgency},origin);
  return {root,bus,origin,post,setTime:t=>now=t};
}

test('oversized queue represents every non-FYI item oldest-first, detail is lossless and reads do not close',async()=>{
  const f=await fixture();const first=await f.post('old-blocker','normal','x'.repeat(4000));
  for(let i=0;i<30;i++){f.setTime(2000+i);await f.post('fyi-'+i,'fyi');await f.post('question-'+i,'normal','y'.repeat(4000));}
  const before=await f.bus.rows();const queue=JSON.parse(await f.bus.inbox({max:1,chars:10}));
  assert.equal(queue.total,31);assert.equal(queue.omitted,0);assert.equal(queue.entries.length,31);
  assert.equal(queue.entries[0].id,first.id);assert.equal(queue.entries[0].text.length,360);
  assert.equal((await f.bus.detail(first.id)).event.text,'x'.repeat(4000));
  assert.deepEqual(await f.bus.rows(),before);
});

test('recorded answer closes question, uncertain delivery remains visible and never replays',async()=>{
  const f=await fixture();const e=await f.post('q');await f.bus.answer(e.id,'Wait; do other authorized work.');
  assert.equal(JSON.parse(await f.bus.inbox()).total,0);let sends=0;
  assert.equal((await f.bus.deliver(e.id,async()=>{sends++;throw Error('unknown admission');})).status,'uncertain-no-replay');
  assert.equal((await f.bus.deliver(e.id,async()=>{sends++;})).status,'already-attempted-no-replay');
  assert.equal(sends,1);assert((await f.bus.status()).uncertainReplies.includes(e.id));
  assert((await f.bus.detail(e.id)).history.some(r=>r.type==='answer'));
});

test('30-minute direct escalation is once under concurrency/failure, answered and FYI items never send',async()=>{
  const f=await fixture();const e=await f.post('old');const answered=await f.post('answered');
  await f.bus.answer(answered.id,'No action.');await f.post('quiet','fyi');let sends=0;
  f.setTime(1000+unansweredEscalationMs-1);await f.bus.escalateUnanswered(async()=>sends++);assert.equal(sends,0);
  f.setTime(1000+unansweredEscalationMs);
  await Promise.all([f.bus.escalateUnanswered(async()=>{sends++;throw Error('unknown');}),f.bus.escalateUnanswered(async()=>sends++)]);
  await f.bus.escalateUnanswered(async()=>sends++);assert.equal(sends,1);
  assert.equal((await f.bus.rows()).filter(r=>r.type==='chief-escalation-attempt'&&r.event===e.id).length,1);
});

test('generic bus answers refuse held/archived/moved recipients; active exact origin receives once',async()=>{
  const f=await fixture();const roster=path.join(f.root,'roster.jsonl');
  let state='hold',archived=false,directory=f.origin.directory,prompts=0;
  const save=()=>writeFile(roster,JSON.stringify({session:f.origin.sessionID,directory:f.origin.directory,state})+'\n');await save();
  const registry=new Map();const session={get:async({sessionID})=>({id:sessionID,agent:'lead',location:{directory:sessionID==='ses_chief'?'/chief':directory},time:{archived:archived?1:undefined}}),
    hook:async()=>({dispose(){}}),prompt:async()=>{prompts++;}};
  const options={enabled:true,deferInitialTick:true,memoryRoot:f.root,rosterFile:roster,originSessions:[f.origin.sessionID],originDirectories:{[f.origin.sessionID]:f.origin.directory},
    fixtureMode:true,chiefSessionID:'ses_chief',chiefDirectory:'/chief',agent:'dispatch',model:{providerID:'fixture',id:'fixture'},chiefInstructions:'No outward effects.',decisions:{}};
  const stop=await setupHeartbeat({options,
    session,tool:{transform:async fn=>{fn({add:t=>registry.set(t.name,t),update:(name,fn)=>fn(registry.get(name))});return{dispose(){}};}}},
    {readAppSession:async origin=>({id:origin.sessionID,location:{directory:origin.directory},time:{}})});
  try{
    // Native chief auth uses an unarchived chief; only the origin carries archive flag.
    session.get=async({sessionID})=>({id:sessionID,agent:'lead',location:{directory:sessionID==='ses_chief'?'/chief':directory},time:{archived:sessionID!=='ses_chief'&&archived?1:undefined}});
    for(const condition of ['held','archived','moved','active']){
      state=condition==='held'?'hold':'active';archived=condition==='archived';directory=condition==='moved'?'/foreign':f.origin.directory;await save();
      const e=await f.post(condition);
      const result=JSON.parse((await registry.get('heartbeat_close').execute({event:e.id,text:'Bound answer.'},{sessionID:'ses_chief'})).content);
      assert.equal(result.delivery.status,condition==='active'?'answer-admitted':'uncertain-no-replay');
      await registry.get('heartbeat_close').execute({event:e.id,text:'Bound answer.'},{sessionID:'ses_chief'});
    }
    assert.equal(prompts,1);
    options.reconciliationRequired=true;
    const parked=await f.post('maintenance-parked','urgent');
    await assert.rejects(registry.get('heartbeat_close').execute({event:parked.id,text:'No replay.'},{sessionID:'ses_chief'}),/reconciliation/);
    await registry.get('chief_post').execute({key:'new-maintenance-post',ref:'new',text:'Record only.',urgency:'urgent'},{sessionID:f.origin.sessionID});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(prompts,1);assert.equal(await f.bus.active(),undefined);
    assert(!(await f.bus.rows()).some(r=>r.type==='chief-escalation-attempt'));
    const before=await f.bus.rows(), actor={sessionID:'ses_chief',messageID:'msg_native',id:'call_native'};
    await assert.rejects(registry.get('heartbeat_close').execute({event:parked.id,text:'Superseded.',mode:'record-only'},
      {...actor,sessionID:'ses_foreign'}),/chief session/);
    const closed=JSON.parse((await registry.get('heartbeat_close').execute({event:parked.id,text:'Superseded.',mode:'record-only'},actor)).content);
    assert.equal(closed.status,'closed-record-only');assert.equal(closed.delivery,'not-attempted');
    assert.deepEqual((await f.bus.rows()).slice(0,before.length),before);
    const after=await f.bus.rows();
    assert.equal(after.length,before.length+1); // Existing answer already closed this item; audit only.
    assert.equal(after.at(-1).type,'chief-record-close');
    await registry.get('heartbeat_close').execute({event:parked.id,text:'Superseded.',mode:'record-only'},actor);
    assert.deepEqual(await f.bus.rows(),after);assert.equal(prompts,1);
    await assert.rejects(f.bus.deliver(parked.id,async()=>{prompts++;}),/record-only/);
    await assert.rejects(registry.get('heartbeat_close').execute({event:'foreign-id',text:'No.',mode:'record-only'},actor),/Exact chief/);
  }finally{await stop();}
});

test('exact timed wake preserves goal and rejects wrong origin, context, cancellation, hold, archive and duplicates',async()=>{
  const f=await fixture();let eligible=true,goal={id:'g',status:'active',objective:'Original outcome.',objectiveFile:false,tokenBudget:42,tokensUsed:7},writes=0;
  let item={id:'dkt_fixture',kind:'timer',fire_at:new Date(2000).toISOString(),status:'pending',target:{session_id:f.origin.sessionID,directory:f.origin.directory},context:{exact:'original'}};
  const waits=new GoalWait(f.bus,{allowedSessions:[f.origin.sessionID],now:()=>3000,checkRecipient:async()=>{if(!eligible)throw Error('held/archived');},checkHolds:async()=>['unchanged hold record'],
    metadata:async(_,__,patch)=>{if(patch){writes++;goal={...goal,...patch.openchamber.goal};}return {openchamber:{goal:{...goal}}};},
    readDocket:async()=>item,messages:async()=>[{id:'admitted',type:'user'}]});
  waits.now=()=>1000;await waits.pauseDocket(item.id,f.origin);waits.now=()=>3000;
  item={...item,status:'delivered',receipt:{admission_id:'admitted'}};
  await assert.rejects(waits.resumeDocket(item.id,{...f.origin,directory:'/wrong'}),/mismatch/);
  const original=item;item={...item,context:{changed:true}};await assert.rejects(waits.resumeDocket(item.id,f.origin),/matching/);
  item={...original,status:'cancelled'};await assert.rejects(waits.resumeDocket(item.id,f.origin),/eligible/);
  item=original;eligible=false;await assert.rejects(waits.resumeDocket(item.id,f.origin),/held/);assert.equal(writes,1);
  eligible=true;assert.equal((await waits.resumeDocket(item.id,f.origin)).status,'resumed-in-current-docket-turn');
  assert.equal((await waits.resumeDocket(item.id,f.origin)).status,'already-attempted-no-replay');
  assert.equal(writes,2);assert.equal(goal.objective,'Original outcome.');assert.equal(goal.tokenBudget,42);assert.equal(goal.tokensUsed,7);
});

test('saved Nod answer stays on exact original once, wrong origin refuses, terminal checks add no journal poll noise',async()=>{
  const f=await fixture();const e=await f.post('nod');
  await f.bus.transaction(async(_,append)=>append({type:'nod-request',mode:'new-bus-only',requestID:'r1',event:e.id,origin:f.origin,ref:'nod',limits:'No new scope.'}));
  const answer={request_id:'r1',status:'answered',decision:{option_id:'wait'}};
  assert.equal((await ingestNodAnswer(f.bus,{requestID:'r1',answer})).status,'queued-chief-no-effects');
  assert.equal((await ingestNodAnswer(f.bus,{requestID:'r1',answer})).status,'duplicate');
  let calls=0;await checkKnown({memoryRoot:f.root,nodReadEnabled:true,nodCommand:['/fixture/no-command']},{run:async()=>{calls++;return JSON.stringify(answer);}});
  assert.equal(calls,0);assert(!(await f.bus.rows()).some(r=>r.type==='nod-check'));
  await f.bus.transaction(async(_,append)=>append({type:'nod-request',mode:'new-bus-only',requestID:'wrong',event:e.id,origin:{...f.origin,sessionID:'ses_foreign'}}));
  await assert.rejects(ingestNodAnswer(f.bus,{requestID:'wrong',answer:{...answer,request_id:'wrong'}}),/origin/);
  const data=(await f.bus.rows()).find(r=>r.type==='nod-answer');assert.deepEqual(data.origin,f.origin);assert.deepEqual(data.answer,answer);
});

test('app archive overlay refuses when native session alone looks active; unknown app state fails closed',async()=>{
  const f=await fixture(),roster=path.join(f.root,'roster.jsonl');
  await writeFile(roster,JSON.stringify({session:f.origin.sessionID,directory:f.origin.directory,state:'active'})+'\n');
  const native={id:f.origin.sessionID,agent:'lead',location:{directory:f.origin.directory},time:{}};
  const session={get:async()=>native};
  for(const app of [{...native,time:{archived:1}}, {...native,time:undefined}, {...native,location:{directory:'/moved'}}]){
    const check=recipientEligibility({rosterFile:roster,session,readAppSession:async()=>app});
    await assert.rejects(check(f.origin),/app recipient/);
  }
  const check=recipientEligibility({rosterFile:roster,session,readAppSession:async()=>native});
  assert.deepEqual(await check(f.origin),{...f.origin,held:false,archived:false});
  await assert.rejects(appSessionReader({})(f.origin),/unavailable/);
  let body;
  const reader=appSessionReader({OPENCHAMBER_AGENT_TOOL_URL:'http://127.0.0.1:1/api/tool',OPENCHAMBER_AGENT_TOOL_TOKEN:'fixture-only'},async(_,input)=>{
    body=JSON.parse(input.body);return{ok:true,json:async()=>({ok:true,data:{sessions:[native]}})};
  });
  assert.equal((await reader(f.origin)).id,f.origin.sessionID);
  assert.equal(body.sessionID,f.origin.sessionID);assert.equal(body.input.all,true);
});
