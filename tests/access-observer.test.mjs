import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp,realpath,readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { setupObserver } from '../access/observer.mjs';

const directory='/fixture/location';
const identity={sessionID:'ses_fixture',agent:'writer',messageID:'msg_fixture',id:'call_fixture',tool:'read'};
const compilation={modelRevision:'fixture',binding:{id:'fixture-writer',role:'writer',home:'/fixture/home',location:directory},
  ruleManifest:[{id:'fixture-deny',reason:'default-deny',action:'read',resource:'blocked.txt',effect:'deny'}]};
const options={enabled:true,candidateOnly:true,directory,bindings:[{sessionID:identity.sessionID,agentID:identity.agent,
  compilation,pathRoots:[{id:'fixture',path:directory}],publicPaths:[directory+'/blocked.txt']}]};
const tick=()=>new Promise(resolve=>setImmediate(resolve)); // Source test scheduling only, never native polling.

async function harness(extra={}) {
  const hooks={},queue=[],rows=[],diagnostics=[];let wake,aborted=false,disposed=0,closed=false;
  const ctx={location:{directory},tool:{async hook(name,handler){hooks[name]=handler;return {async dispose(){disposed++;delete hooks[name];}};}},
    permission:{reply(){throw Error('MUST NEVER REPLY');},assert(){throw Error('MUST NEVER ASSERT');}},
    session:{update(){throw Error('MUST NEVER UPDATE');},prompt(){throw Error('MUST NEVER PROMPT');}},
    event:{async *subscribe({signal}) {
      const onAbort=()=>{aborted=true;wake?.();};signal.addEventListener('abort',onAbort,{once:true});
      try {while(!signal.aborted){if(!queue.length) await new Promise(resolve=>{wake=resolve;});while(queue.length) yield queue.shift();}}
      finally {signal.removeEventListener('abort',onAbort);}
    }}};
  const seen=new Set();
  const sink={async append(row){const key=row.source.call??row.id;if(seen.has(key))return {status:'duplicate'};
    seen.add(key);rows.push(row);return {status:'appended'};},async close(){closed=true;}};
  const observer=await setupObserver(ctx,{...options,...extra},{openLog:async()=>sink,diagnostic:code=>diagnostics.push(code)});
  return {ctx,hooks,rows,diagnostics,observer,sink,async event(event){queue.push(event);wake?.();await tick();},
    state:()=>({aborted,disposed,closed})};
}

function asked(overrides={}) {
  return {type:'permission.asked',id:'evt_asked',location:{directory},data:{id:'per_fixture',sessionID:'ses_fixture',
    action:'read',resources:['blocked.txt'],source:{type:'tool',messageID:'msg_fixture',id:'call_fixture'},...overrides}};
}
function replied(overrides={}) {
  return {type:'permission.replied',id:'evt_replied',location:{directory},data:{sessionID:'ses_fixture',requestID:'per_fixture',reply:'reject',...overrides}};
}

test('disabled default performs zero registration/subscription/file operations',async()=>{
  const ctx=new Proxy({}, {get(){throw Error('disabled observer touched host');}});
  const o=await setupObserver(ctx,{});assert.equal(o.enabled,false);await o.close();
});

test('proved plain rejection event seam records native action/path without inventing configured rule',async()=>{
  const h=await harness();await h.hooks['execute.before']({...identity,input:{path:'blocked.txt',env:{TOKEN:'FAKE_SECRET'}}});
  await h.event(asked());assert.equal(h.rows.length,0);
  await h.event(replied());assert.equal(h.rows.length,1);
  const r=h.rows[0];assert.equal(r.role,'writer');assert.equal(r.action,'read');assert.equal(r.path.value,'@fixture/blocked.txt');
  assert.equal(r.ruleEvidence,'native-asked-and-replied-reject');assert.equal(r.denyingRule,null);
  assert.equal(r.source.request,'per_fixture');assert.equal(r.roleEvidence,'explicit-binding-and-native-call');
  assert.ok(!JSON.stringify(r).includes('FAKE_SECRET'));assert.equal(h.observer.status().pendingCalls,0);
  await h.observer.close();assert.deepEqual(h.state(),{aborted:true,disposed:2,closed:true});
});

test('configured deny via after hook and a later correlated event do not emit twice',async()=>{
  const h=await harness();await h.hooks['execute.before'](identity);await h.event(asked());
  await h.hooks['execute.after']({...identity,status:'error',error:{error:{_tag:'Permission.BlockedError',permission:'read',
    resources:['blocked.txt'],rules:[compilation.ruleManifest[0]]}}});
  await h.event(replied());assert.equal(h.rows.length,1);assert.equal(h.rows[0].denyingRule.id,'fixture-deny');
  assert.equal(h.observer.status().duplicates,1);await h.observer.close();
});

test('aborted alone, ordinary errors, approvals and foreign events are not denials',async()=>{
  const h=await harness();
  await h.hooks['execute.after']({...identity,status:'error',error:{type:'aborted',message:'Permission denied'}});
  await h.event({...asked(),location:{directory:'/foreign'}});
  await h.event({...replied(),location:{directory:'/foreign'}});
  assert.equal(h.rows.length,0);await h.hooks['execute.before'](identity);await h.event(asked());
  await h.event(replied({reply:'once'}));assert.equal(h.rows.length,0);assert.equal(h.observer.status().pendingRequests,0);
  await h.observer.close();
});

test('missing before binding stays unknown; wrong-session replies cannot acquire another request metadata',async()=>{
  const h=await harness();await h.event(asked());await h.event(replied({sessionID:'ses_other'}));
  assert.equal(h.rows[0].action,null);assert.equal(h.rows[0].role,'unbound');assert.equal(h.rows[0].source.call,null);
  await h.event(replied());assert.equal(h.rows[1].action,'read');assert.equal(h.rows[1].role,'unbound');
  assert.equal(h.rows[1].path.value,null);assert.equal(h.rows[1].denyingRule,null);await h.observer.close();
});

test('unbound after denials still logged, without leaking command/env/error/raw rules',async()=>{
  const h=await harness();await h.hooks['execute.after']({...identity,agent:'other',tool:'shell',status:'error',
    input:{command:'FAKE_COMMAND',env:{TOKEN:'FAKE_ENV'}},error:{message:'FAKE_MESSAGE',error:{_tag:'Permission.BlockedError',
      permission:'shell',resources:['FAKE_COMMAND'],rules:[{action:'shell',resource:'FAKE_COMMAND',effect:'deny'}]}}});
  assert.equal(h.rows[0].role,'unbound');assert.equal(h.rows[0].action,'shell');assert.equal(h.rows[0].path.value,null);
  assert.equal(h.rows[0].denyingRule,null);assert.ok(!JSON.stringify(h.rows).includes('FAKE_'));await h.observer.close();
});

test('bounded pending map evicts explicitly and a later unmatched rejection stays unknown',async()=>{
  const h=await harness();for(let i=0;i<257;i++) await h.event(asked({id:'per_'+i,source:undefined}));
  assert.equal(h.observer.status().pendingRequests,256);assert.equal(h.observer.status().evictions,1);
  await h.event(replied({requestID:'per_0'}));assert.equal(h.rows[0].action,null);
  assert.equal(h.rows[0].ruleEvidence,'native-reject-without-observed-request');await h.observer.close();
});

test('sink failure is observable diagnostic loss without throwing into a denied tool or retrying',async()=>{
  const h=await harness();let attempts=0;h.sink.append=async()=>{attempts++;throw Error('PRIVATE_ERROR');};
  await h.hooks['execute.after']({...identity,status:'error',error:{type:'permission.rejected'}});
  assert.equal(attempts,1);assert.equal(h.observer.status().diagnosticLoss,1);
  assert.deepEqual(h.diagnostics,['denial-log-append-failed']);await h.observer.close();
});

test('failed rejection append retains bounded correlation for a separately delivered event',async()=>{
  const h=await harness();const append=h.sink.append;let attempts=0;
  h.sink.append=async row=>{if(++attempts===1)throw Error('PRIVATE_STORAGE_ERROR');return append(row);};
  try {
    await h.hooks['execute.before'](identity);await h.event(asked());await h.event(replied());
    assert.equal(h.observer.status().observed,0);assert.equal(h.observer.status().loggingAvailable,false);
    assert.equal(h.observer.status().pendingRequests,1);assert.equal(h.observer.status().pendingCalls,1);
    assert.deepEqual(h.diagnostics,['denial-log-append-failed']);await tick();assert.equal(attempts,1);
    await h.event(replied());assert.equal(attempts,2);assert.equal(h.rows.length,1);
    assert.equal(h.rows[0].role,'writer');assert.equal(h.rows[0].roleEvidence,'explicit-binding-and-native-call');
    assert.equal(h.observer.status().loggingAvailable,true);assert.equal(h.observer.status().pendingRequests,0);
    assert.equal(h.observer.status().pendingCalls,0);assert.ok(!JSON.stringify(h.rows).includes('PRIVATE_STORAGE_ERROR'));
  } finally {await h.observer.close();}
});

test('actual private sink correlates native call despite unknown tool label on event fallback',async()=>{
  const {denialLog}=await import('../access/denial-log.mjs');
  const root=await mkdtemp(path.join(await realpath(tmpdir()),'observer-sink-'));
  const file=root+'/denials.jsonl',sink=await denialLog(file);
  const common={type:'permission-denial',source:{session:'ses_x',message:'msg_x',call:'call_x'}};
  assert.equal((await sink.append({...common,id:'a'.repeat(64),tool:'read'})).status,'appended');
  assert.equal((await sink.append({...common,id:'b'.repeat(64),tool:null})).status,'duplicate');
  await sink.close();assert.equal((await readFile(file,'utf8')).trim().split('\n').length,1);
});

test('synthetic native rejection envelope supports event attribution but never an after-hook claim',async()=>{
  // Same event/source fields, not a private native proof or host-acceptance claim.
  const proof=JSON.parse(await readFile(new URL('./fixtures/access/native-rejection.json',import.meta.url),'utf8'));
  assert.equal(proof.executeAfterSeen,false);assert.equal(proof.persistedErrorType,'aborted');
  const h=await harness({bindings:[]});
  const nativeCall={sessionID:proof.session,agent:proof.agent,tool:'read',messageID:proof.source.messageID,id:proof.source.id};
  await h.hooks['execute.before'](nativeCall);
  await h.event({type:'permission.asked',id:proof.nativeAskedEvent,data:{id:proof.requestID,sessionID:proof.session,
    action:proof.action,resources:['ask-deny.txt'],source:{type:'tool',...proof.source}}});
  await h.event({type:'permission.replied',id:proof.nativeRejectedEvent,data:{sessionID:proof.session,requestID:proof.requestID,reply:'reject'}});
  assert.equal(h.rows.length,1);assert.equal(h.rows[0].action,'read');assert.equal(h.rows[0].denyingRule,null);
  assert.equal(h.rows[0].role,'unbound');await h.observer.close();
});

test('partial setup failure disposes owned hooks and closes sink without changing permissions',async()=>{
  let hooks=0,disposed=0,closed=0;
  const ctx={location:{directory},tool:{async hook(){if(++hooks===2)throw Error('setup');return {async dispose(){disposed++;}};}},
    event:{subscribe(){throw Error('must not subscribe after failed setup');}}};
  await assert.rejects(setupObserver(ctx,options,{openLog:async()=>({async close(){closed++;}})}),/setup failed/);
  assert.equal(disposed,1);assert.equal(closed,1);
});

test('event stream failure records bounded diagnostic loss, does not retry or affect after-hook denials',async()=>{
  const hooks={},rows=[];let subscriptions=0;
  const ctx={location:{directory},tool:{async hook(name,fn){hooks[name]=fn;return {async dispose(){}};}},
    event:{async *subscribe(){subscriptions++;throw Error('RAW_PRIVATE_STREAM_ERROR');}}};
  const diag=[];
  const observer=await setupObserver(ctx,options,{openLog:async()=>({async append(row){rows.push(row);return {status:'appended'};},async close(){}}),diagnostic:code=>diag.push(code)});
  await tick();assert.equal(subscriptions,1);assert.deepEqual(diag,['denial-event-stream-failed']);
  await hooks['execute.after']({...identity,status:'error',error:{type:'permission.rejected'}});
  assert.equal(rows.length,1);assert.equal(rows[0].denyingRule,null);await observer.close();
});

test('non-tool native reject retains observed action but cannot borrow tool provenance or a role',async()=>{
  const h=await harness();await h.hooks['execute.before'](identity);
  await h.event(asked({source:{type:'other',id:identity.id,messageID:identity.messageID}}));
  await h.event(replied());assert.equal(h.rows[0].action,'read');assert.equal(h.rows[0].role,'unbound');
  assert.equal(h.rows[0].source.call,null);assert.equal(h.rows[0].source.message,null);
  assert.equal(h.rows[0].denyingRule,null);await h.observer.close();
});
