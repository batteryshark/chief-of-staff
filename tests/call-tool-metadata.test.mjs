import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveNativeCaller} from '../services/voicestack/opencode.js';

const invocation = () => ({sessionID:'ses_nativeCaller',agent:'build',signal:new AbortController().signal});
const info = () => ({id:'ses_nativeCaller',agent:'build',projectID:'native-project',location:{directory:'/actual/current/project'}});
const unavailable = {message:'Native caller metadata unavailable'};

test('native quartet comes from current session, not plugin location or caller overrides', async () => {
  let current=info(), reads=0;
  const ctx={get location(){throw Error('plugin-instance location must not be read');},
    session:{async get(input, options){
      reads++; assert.deepEqual(input,{sessionID:'ses_nativeCaller'});
      assert.ok(options.signal instanceof AbortSignal); return current;
    }}};
  const c={...invocation(),projectID:'spoof',directory:'/spoof',role:'chief',context:{directory:'/spoof'}};
  const result=await resolveNativeCaller(ctx,c);
  assert.deepEqual(result,{session_id:'ses_nativeCaller',agent_id:'build',project_id:'native-project',directory:'/actual/current/project'});
  assert.ok(Object.isFrozen(result));
  current={...info(),projectID:'moved-project',location:{directory:'/moved/project'}};
  assert.equal((await resolveNativeCaller(ctx,c)).directory,'/moved/project');
  assert.equal(reads,2); // no cached location
  assert.equal(result.directory,'/actual/current/project');
});

test('wrong/missing native identity or location fails closed without fallback', async () => {
  for (const value of [null,{data:info()}, {...info(),id:'ses_wrong'}, {...info(),agent:'other'},
    {...info(),agent:undefined}, {...info(),projectID:undefined}, {...info(),projectID:'invalid/project'},
    {...info(),location:undefined}, {...info(),location:{directory:'relative'}},
    {...info(),location:{directory:'/unsafe/../directory'}}, {...info(),location:{directory:''}}]) {
    await assert.rejects(resolveNativeCaller({location:{directory:'/fallback',project:{id:'fallback'}},
      session:{get:async () => value}},invocation()),unavailable);
  }
  let reads=0;
  const ctx={session:{get:async () => {reads++;return info();}}};
  for (const c of [{...invocation(),sessionID:'bad'}, {...invocation(),agent:''}, {...invocation(),signal:undefined}])
    await assert.rejects(resolveNativeCaller(ctx,c),unavailable);
  assert.equal(reads,0);
});

test('cancellation, timeout and native errors are bounded and sanitized', async () => {
  const controller=new AbortController(); controller.abort();
  await assert.rejects(resolveNativeCaller({session:{get(){throw Error('must not read');}}},
    {...invocation(),signal:controller.signal}),unavailable);
  let requestSignal;
  const pending={session:{get:async (_input,{signal}) => {requestSignal=signal;return new Promise(() => {});}}};
  const cancel=new AbortController();
  const result=resolveNativeCaller(pending,{...invocation(),signal:cancel.signal});
  cancel.abort();
  await assert.rejects(result,unavailable);
  assert.equal(requestSignal.aborted,true);
  const started=Date.now();
  await assert.rejects(resolveNativeCaller(pending,invocation()),unavailable);
  assert.ok(Date.now()-started<2000); assert.equal(requestSignal.aborted,true);
  await assert.rejects(resolveNativeCaller({session:{get:async () => {throw Error('private detail');}}},invocation()),unavailable);
});
