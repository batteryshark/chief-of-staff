import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { Bus } from './bus.mjs';
import { checkKnown } from './nod-feed.mjs';
import { GoalWait } from './goal-wait.mjs';
import { standingPolicy } from './records.mjs';
import { setupHeartbeat, toolDescriptions } from './plugin.mjs';
import { resolvedObjective } from './objective.mjs';

test('file-mode waits bind effective objective and reject changed file before resume without touching real goals', async () => {
  const root=await mkdtemp(path.join(os.tmpdir(),'heartbeat-effective-')), sid='ses_owned', file=path.join(root,'goals',sid+'.md');
  await mkdir(path.dirname(file));const text='Goal: reviewed outcome.\n\nHistorical handover, superseded by current stops.';
  await writeFile(file,text+'\n');
  const binding={id:'owned',objective:'',objectiveFile:true,objectiveFilePath:file,effectiveObjectiveSha256:createHash('sha256').update(text).digest('hex')};
  const resolved=await resolvedObjective({objective:'',objectiveFile:true},sid,binding,{OPENCHAMBER_DATA_DIR:root});
  assert.equal(resolved.text,text);assert.equal(resolved.source,file);
  await assert.rejects(resolvedObjective({objective:'',objectiveFile:true},sid,binding,{OPENCHAMBER_DATA_DIR:path.join(root,'wrong')}),/data directory/);
  const old=process.env.OPENCHAMBER_DATA_DIR;process.env.OPENCHAMBER_DATA_DIR=root;
  try {
    const bus=new Bus(path.join(root,'bus')), event=await bus.post({key:'real',ref:'scope',text:'normal question',urgency:'normal'},{sessionID:sid,directory:'/reset'});
    let goal={id:'owned',objective:'',objectiveFile:true,status:'active',tokenBudget:42,tokensUsed:7},writes=0;
    const waits=new GoalWait(bus,{checkRecipient:async()=>{},allowedSessions:[sid],goalBindings:{[sid]:binding},checkHolds:async()=>['exact stops and Goal'],metadata:async(_,__,patch)=>{
      if(patch){goal={...goal,...patch.openchamber.goal};writes++;}return {openchamber:{goal:{...goal}}};
    }});
    const wait=await waits.pause(event.id,{sessionID:sid,directory:'/reset',lane:'reset'});
    assert.equal(wait.objective,text);assert.equal(wait.inlineObjective,'');assert.equal(wait.effectiveObjectiveSha256,binding.effectiveObjectiveSha256);
    await writeFile(file,'Goal: changed scope.');await assert.rejects(waits.wake(event.id,'answer'),/reviewed scope/);
    assert.equal(writes,1);assert.equal(goal.status,'paused');assert.equal(goal.tokensUsed,7);assert.equal(goal.objective,'');
  } finally {if(old===undefined)delete process.env.OPENCHAMBER_DATA_DIR;else process.env.OPENCHAMBER_DATA_DIR=old;}
});

test('new known-ID feed is bounded, preserves exact answers and never calls ask/deliver', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'heartbeat-feed-')), bus = new Bus(root);
  await bus.transaction(async (_, append) => {
    for (let i=0; i<6; i++) {
      await append({ type:'post', id:`e${i}`, origin:{sessionID:'ses_lead',directory:'/lead'},ref:'real',at:1 });
      await append({ type:'result', event:`e${i}`, route:'principal', text:'needs judgment' });
      await append({ type:'nod-request', mode:'new-bus-only', requestID:`r${i}`,event:`e${i}`,origin:{sessionID:'ses_lead',directory:'/lead'},ref:'real',limits:'no new scope' });
    }
    await append({type:'nod-request',mode:'legacy',requestID:'legacy',event:'e0'});
  });
  const calls=[];
  const answer = rid => ({ request_id:rid,status:'pending',decision:null,decisions:[{option_id:'notes',text:'not approval',created_at:'exact'}] });
  const run=async (_, args) => { assert.equal(args[0],'decision-json');calls.push(args[1]);return JSON.stringify(answer(args[1])); };
  const options={memoryRoot:root,nodReadEnabled:true,nodCommand:['/installed/chief-nod']};
  const result=await checkKnown(options,{run,now:()=>100});assert.equal(result.checked,4);assert.equal(calls.length,4);assert(!calls.includes('legacy'));
  const rows=await bus.rows();assert.deepEqual(rows.find(r=>r.type==='nod-answer').answer,answer('r0'));
  assert.equal(rows.filter(r=>r.type==='result'&&r.route==='chief').length,4);
  const next=await checkKnown(options,{run,now:()=>101});assert.equal(next.checked,2);assert.deepEqual(calls.slice(4),['r4','r5']);
});

test('installed chief metadata is stripped and policy remains bounded existing-file evidence', async () => {
  const root=await mkdtemp(path.join(os.tmpdir(),'heartbeat-policy-'));
  const file=path.join(root,'chief.md'), policy=path.join(root,'records.md');
  await writeFile(file,'---\npermissions: NEVER EMBED\n---\nChief role only.\n');
  await writeFile(policy,'## Decisions\nAccepted narrow scope.\n\n'+ 'omitted '.repeat(1000));
  const result=await standingPolicy({chiefInstructionsFile:file,standingSections:[{file:policy,heading:'## Decisions',maxChars:128}]});
  assert.equal(result.instructions,'Chief role only.');assert(!result.instructions.includes('permissions'));
  assert.equal(result.sources[0].omittedParagraphs,1);
});

test('reviewed goal ID and objective-file scope refuse changes before any write', async () => {
  const root=await mkdtemp(path.join(os.tmpdir(),'heartbeat-goal-')), bus=new Bus(root);
  const event=await bus.post({key:'one',ref:'real',urgency:'normal',text:'real ask'},{sessionID:'ses_lead',directory:'/lead'});
  let writes=0;
  const waits=new GoalWait(bus,{checkRecipient:async()=>{},allowedSessions:['ses_lead'],goalBindings:{ses_lead:{id:'reviewed',objective:'',objectiveFile:true}},
    metadata:async (_,__,patch)=> { if(patch) writes++;return {openchamber:{goal:{id:'different',status:'active',objective:'',objectiveFile:true}}}; },checkHolds:async()=>['exact reviewed Goal/Stop conditions']});
  await assert.rejects(waits.pause(event.id,{sessionID:'ses_lead',directory:'/lead',lane:'reset'}),/reviewed scope/);
  assert.equal(writes,0);
});

test('enabled runtime filters tool catalogs by exact recipient without creating work on an empty bus', async () => {
  const root=await mkdtemp(path.join(os.tmpdir(),'heartbeat-ctx-')), registry=new Map(), hooks=[];
  const ctx={options:{enabled:true,memoryRoot:root,fixtureMode:true,chiefSessionID:'ses_chief',chiefDirectory:'/chief',agent:'dispatch',model:{providerID:'openai',id:'gpt-6-luna',variant:'medium'},chiefInstructions:'Chief',decisions:{d:'Accepted'},originSessions:['ses_lead'],goalSessions:['ses_lead'],docketSource:'/existing/docket'},
    location:{directory:'/chief'},tool:{transform:async fn=>{fn({add:t=>registry.set(t.name,t),update:(name,fn)=>fn(registry.get(name))});return {dispose:async()=>{}};}},
    session:{get:async()=>({data:{id:'ses_chief',location:{directory:'/chief'}}}),hook:async(_,hook)=>{hooks.push(hook);return{dispose:async()=>{}};},create:async()=>{throw Error('empty bus must not create');}}};
  const stop=await setupHeartbeat(ctx,{onError:e=>{throw e;}});
  try {
    const event=sid=>({sessionID:sid,tools:Object.fromEntries([...registry.keys()].map(k=>[k,{}])),system:[],options:{}});
    const chief=event('ses_chief');await hooks[0](chief);assert.deepEqual(Object.keys(chief.tools).sort(),['heartbeat_close','heartbeat_reconcile','heartbeat_status']);assert.equal(chief.system.length,1);
    const lead=event('ses_lead');await hooks[0](lead);assert.deepEqual(Object.keys(lead.tools),['chief_post','chief_wait','chief_wait_time','chief_resume_time']);assert.equal(lead.system.length,0);
    const other=event('ses_other');await hooks[0](other);assert.deepEqual(other.tools,{});
    for(const [name,description] of Object.entries(toolDescriptions)) assert.equal(registry.get(name).description,description);
    assert.deepEqual(registry.get('chief_post').input.required,['urgency','text','ref','key']);
    assert.equal(registry.get('chief_post').input.properties.limits.type,'string');
  } finally {await stop();}
});
