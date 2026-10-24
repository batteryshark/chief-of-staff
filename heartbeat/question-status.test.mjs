import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {Bus} from './bus.mjs';
import {snapshot, captureQuestionOrigin, requestOK} from './question-status.mjs';
const at = Date.now()-10000;
const q = {version:1,session:'ses_test',directory:'/approved/project',goal:{id:'goal_test',created_at:at-1000}};
const coverage = {version:1,scope:'registered-chief-post',since:at-2000,origins:[{session:q.session,directory:q.directory}]};
const origin = {sessionID:q.session,directory:q.directory,goal:q.goal};
async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(),'question-status-'));
  const bus = new Bus(root,{now:()=>at});
  return {root,bus,post:(key,who=origin)=>bus.post({urgency:'normal',text:'PRIVATE QUESTION BODY',ref:'private-ref',key},who)};
}
test('native createdAt milliseconds captured without caller-supplied goal or writes', async()=>{
  const caller = {id:q.session,location:{directory:q.directory}};
  let args;
  const result = await captureQuestionOrigin(caller,q.session,async(...a)=>{args=a;return {openchamber:{goal:{id:q.goal.id,createdAt:q.goal.created_at}}};});
  assert.deepEqual(result,origin); assert.deepEqual(args,[q.session,q.directory]);
  assert.equal((await captureQuestionOrigin(caller,q.session,async()=>({openchamber:{goal:{id:'g',created_at:at}}}))).goal,undefined);
  assert.equal((await captureQuestionOrigin(caller,q.session,async()=>{throw Error();})).goal,undefined);
  await assert.rejects(captureQuestionOrigin(caller,'ses_other',async()=>{}));
});
test('missing/unknown coverage and missing journal never fabricate zero; strict nested request',async()=>{
  const {bus}=await fixture();
  assert.equal((await snapshot(bus,q,coverage)).complete,false);
  assert.equal((await snapshot(bus,q,undefined)).complete,false);
  for (const bad of [{...q,other:1},{...q,goal:{...q.goal,other:1}},{...q,goal:{id:'g',created_at:true}},{...q,directory:'/x/../project'}]) assert.equal(requestOK(bad),false);
});
test('observed installation boundary supports old goals but not precoverage unresolved posts',async()=>{
  const f=await fixture(); await f.post('bound');
  const installed={...coverage,since:at};
  const out=await snapshot(f.bus,q,installed,at+1000);
  assert.equal(out.complete,true); assert.equal(out.questions.length,1);
  assert.equal((await snapshot(f.bus,q,{...installed,since:at+1},at+1000)).complete,false);
  assert.equal((await snapshot(f.bus,q,{...installed,since:at+2000},at+1000)).complete,false);
  const legacy=await fixture(); await legacy.post('legacy',{sessionID:q.session,directory:q.directory});
  assert.equal((await snapshot(legacy.bus,q,installed,at+1000)).complete,false);
});
test('zero/one/multiple and lifecycle read-only; answer uncertainty is not unresolved',async()=>{
  const f=await fixture(); const e=await f.post('one');
  const before=await readFile(path.join(f.root,'events.jsonl'),'utf8');
  const one=await snapshot(f.bus,q,coverage);
  assert.equal(one.complete,true); assert.equal(one.questions.length,1);
  assert(!JSON.stringify(one).includes('PRIVATE')); assert(!JSON.stringify(one).includes('private-ref'));
  assert.equal(await readFile(path.join(f.root,'events.jsonl'),'utf8'),before);
  await f.post('two'); assert.equal((await snapshot(f.bus,q,coverage)).questions.length,2);
  await f.bus.answer(e.id,'saved');
  await f.bus.deliver(e.id,async()=>{throw Error('uncertain');});
  assert.equal((await snapshot(f.bus,q,coverage)).questions.length,1);
  const second=JSON.parse(await f.bus.inbox()).entries[0]; await f.bus.answer(second.id,'closed');
  const zero=await snapshot(f.bus,q,coverage); assert.equal(zero.complete,true); assert.equal(zero.questions.length,0);
});
test('legacy, changed directory, unknown lifecycle and overlimit fail closed',async()=>{
  for (const who of [{sessionID:q.session,directory:q.directory},{...origin,directory:'/moved'}]) {
    const f=await fixture(); await f.post('legacy',who); assert.equal((await snapshot(f.bus,q,coverage)).complete,false);
  }
  const f=await fixture(); await f.post('oldgoal',{...origin,goal:{id:'old',created_at:at-2000}});
  assert.equal((await snapshot(f.bus,q,coverage)).questions.length,0);
  const inbox={sourceComplete:true,total:201,omitted:0,entries:Array(201).fill({})};
  assert.equal((await snapshot({inbox:async()=>JSON.stringify(inbox)},q,coverage)).complete,false);
  assert.equal((await snapshot({inbox:async()=>{throw Error();}},q,coverage)).complete,false);
  const e=await f.post('unknown'); await f.bus.transaction(async(_,append)=>append({type:'result',event:e.id,route:'future'}));
  assert.equal((await snapshot(f.bus,q,coverage)).complete,false);
});
test('CLI rejects overrides/oversized/malformed input without output or side effects',()=>{
  for (const [args,input] of [[[],'x'.repeat(4097)],[[],'{}'],[['--options','/foreign'],'{}']]) {
    const r=spawnSync(process.execPath,['heartbeat/chief-question-status.mjs',...args],{input,encoding:'utf8'});
    assert.notEqual(r.status,0); assert.equal(r.stdout,''); assert.equal(r.stderr,'');
  }
});
test('32KiB overlimit returns incomplete, never a truncated surviving question',async()=>{
  const entries=Array.from({length:180},(_,i)=>({id:'00000000-0000-4000-8000-'+String(i).padStart(12,'0'),origin}));
  const bus={inbox:async()=>JSON.stringify({sourceComplete:true,total:entries.length,omitted:0,entries}),
    detail:async id=>({event:{id,origin,at,urgency:'normal'},history:[]})};
  const out=await snapshot(bus,q,coverage);
  assert.equal(out.complete,false); assert.deepEqual(out.questions,[]);
});
test('CLI fixed installed options reads synthetic bus without mutating it or disclosing question text',async()=>{
  const f=await fixture(); await f.post('one');
  const home=await mkdtemp(path.join(os.tmpdir(),'question-status-home-'));
  const dir=path.join(home,'.chief-of-staff/heartbeat'); await mkdir(dir,{recursive:true});
  await writeFile(path.join(dir,'pilot-options.json'),JSON.stringify({memoryRoot:f.root,questionCoverage:coverage}),{mode:0o600});
  const before=await readFile(path.join(f.root,'events.jsonl'),'utf8');
  const result=spawnSync(process.execPath,['heartbeat/chief-question-status.mjs'],{input:JSON.stringify(q),encoding:'utf8',env:{...process.env,HOME:home},timeout:5000});
  assert.equal(result.status,0); const out=JSON.parse(result.stdout);
  assert.equal(out.complete,true); assert.equal(out.questions.length,1); assert(!result.stdout.includes('PRIVATE'));
  assert.equal(await readFile(path.join(f.root,'events.jsonl'),'utf8'),before);
});
