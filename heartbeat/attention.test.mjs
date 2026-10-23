import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { Bus, state } from './bus.mjs';
import { attentionDelivery } from './attention.mjs';
import { NodAdapter, ingestNodAnswer } from './nod.mjs';
import { setupHeartbeat } from './plugin.mjs';

async function item(route='principal',urgency='urgent') {
  const root=await mkdtemp(path.join(os.tmpdir(),'attention-unit-')),bus=new Bus(root,{now:()=>100});
  const limits='Read-only scope; no purchase, publishing or goal change. '.repeat(60);
  const e=await bus.post({key:'real-scope',ref:'original-ref',urgency,text:'Owner needs a decision.',limits},{sessionID:'ses_original',directory:'/project'});
  const batch=await bus.claim();
  if(batch){await bus.bind(batch.id,'ses_dispatch');await bus.resolve({sessionID:'ses_dispatch',event:e.id,route,text:'Need judgment.'},{decisions:{}});}
  return {bus,e,limits};
}
const options={nodSendEnabled:true,nodNotBefore:1,nodCommand:['/installed/chief-nod']};

test('all origin decisions remain in chief inbox; urgent delivery never creates a principal card',async()=>{
  for(const route of ['principal','chief']) {
    const {bus,e,limits}=await item(route);let calls=0;
    const before=await bus.rows();
    const send=attentionDelivery(options,{run:async()=>{calls++;throw Error('must never send');}});
    assert.equal((await send({bus,event:e.id,text:'Review'})).status,'chief-judgment-pending');
    await send({bus,event:e.id,text:'Repeated callback'});
    assert.equal(calls,0);assert.deepEqual(await bus.rows(),before);
    const stored=state(before).events[0];assert.equal(stored.result.route,'chief');assert.equal(stored.limits,limits);
    assert.deepEqual(stored.origin,e.origin);assert.equal(stored.ref,e.ref);assert(!stored.closed);
    assert((await bus.inbox()).includes(e.ref));
  }
});

test('retired bus creation refuses before intent, mapping or transport',async()=>{
  const {bus,e}=await item();const before=await bus.rows();let calls=0;
  const adapter=new NodAdapter(bus,{command:options.nodCommand,run:async()=>{calls++;}});
  await assert.rejects(adapter.ask({event:e.id,title:'Decision?',summary:'Choose',limits:'Exact'}),/chief judgment/);
  assert.equal(calls,0);assert.deepEqual(await bus.rows(),before);
});

test('historical cards, pending/uncertain effects and raw answer provenance stay intact',async()=>{
  const {bus,e,limits}=await item();
  await bus.transaction(async(_,append)=>{
    await append({type:'nod-intent',event:e.id,mode:'new-bus-only',origin:e.origin,ref:e.ref,limits});
    await append({type:'nod-request',event:e.id,requestID:'old',mode:'new-bus-only',origin:e.origin,ref:e.ref,limits});
    await append({type:'result',event:e.id,route:'principal',effect:'nod-uncertain-no-replay',text:'Historical uncertainty'});
  });
  const before=await bus.rows();let calls=0;
  await attentionDelivery(options,{run:async()=>{calls++;}})({bus,event:e.id,text:'Old item'});
  assert.deepEqual(await bus.rows(),before);assert.equal(calls,0);
  const answer={request_id:'old',decision:{option_id:'discuss',text:'Historical answer data'}};
  await ingestNodAnswer(bus,{requestID:'old',answer});
  const rows=await bus.rows();assert.deepEqual(rows.slice(0,before.length),before);
  assert.deepEqual(rows.find(r=>r.type==='nod-answer').answer,answer);
  assert.equal(rows.find(r=>r.type==='nod-answer').limits,limits);
  assert(!rows.some(r=>['answer','goal-woken','goal-wake-attempt','close'].includes(r.type)));
});

test('production resolver normalizes principal to chief without invoking configured callbacks',async()=>{
  const {bus,e}=await item(),registry=new Map();let calls=0;
  const ctx={options:{enabled:true,memoryRoot:bus.root,fixtureMode:true,chiefSessionID:'ses_chief',agent:'dispatch',model:{providerID:'openai',id:'gpt-6-luna'},chiefInstructions:'Chief',decisions:{d:'Standing'},deferInitialTick:true},
    location:{directory:'/chief'},tool:{transform:async fn=>{fn({add:t=>registry.set(t.name,t),update:(name,edit)=>edit(registry.get(name))});return{dispose:async()=>{}};}},
    session:{hook:async()=>({dispose:async()=>{}})}};
  const stop=await setupHeartbeat(ctx,{principalDelivery:async()=>{calls++;},chiefAttention:async()=>{calls++;}});
  try {
    const response=JSON.parse((await registry.get('heartbeat_resolve').execute({event:e.ref,route:'principal',text:'Decision needed',decision:'',quote:''},{sessionID:'ses_dispatch'})).content);
    assert.equal(response.event,e.id);assert.equal(response.route,'chief');assert.equal(response.delivery.status,'chief-judgment-pending');
    assert.equal(calls,0);assert(!(await bus.rows()).some(r=>r.type.startsWith('nod-')));
  } finally {await stop();}
});

test('optional original limits preserve four-field posts and stable-key identity',async()=>{
  const {bus,e}=await item();
  await assert.rejects(bus.post({key:e.key,ref:e.ref,urgency:e.urgency,text:e.text,limits:'different'},e.origin),/payload conflict/);
  const plain={key:'old-four-field',ref:'status',urgency:'fyi',text:'Quiet milestone'};
  const first=await bus.post(plain,e.origin),again=await bus.post(plain,e.origin);assert.equal(first.id,again.id);assert(!('limits' in first));
});
