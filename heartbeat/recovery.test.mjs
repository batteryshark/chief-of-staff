import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { Bus, state, claimDeadlineMs, questionFallbackMs } from './bus.mjs';
import { maintainClaim, dispatchItems } from './plugin.mjs';

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'heartbeat-recovery-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  let now = 1000;
  const bus = new Bus(root, { now: () => now });
  const origin = { sessionID: 'ses_origin', directory: '/original' };
  const post = (key, ref = key) => bus.post({ urgency: 'urgent', text: 'Existing question DATA', ref, key }, origin);
  const calls = [];
  let busy = false, unavailable = false, uncertain = false;
  const ctx = { session: {
    get: async () => ({ id:'ses_child', parentID:'ses_chief', metadata:{ heartbeatDispatcher:true } }),
    wait: async () => {
      if (unavailable) throw Error('native unavailable');
      if (busy) throw Object.assign(Error('still active'), { name:'TimeoutError' });
    },
    interrupt: async input => { calls.push(input); if (uncertain) throw Error('lost cancellation response'); busy = false; },
  } };
  const chief = { current: async () => ({session:'ses_chief'}) };
  const maintain = () => maintainClaim(bus, ctx, chief, {now:() => now});
  const bind = async batch => { await bus.bind(batch.id,'ses_child','ses_chief'); await bus.promptStage(batch.id,'admitted'); };
  return { bus, post, bind, ctx, calls, maintain, setTime:v=>now=v,
    setBusy:v=>busy=v, setUnavailable:v=>unavailable=v, setUncertain:v=>uncertain=v };
}

test('EXACT mistaken ref resolves only this bound member and preserves canonical UUID internally', async t => {
  const f = await fixture(t), id = '00000000-0000-4000-8000-000000000004';
  await f.bus.transaction(async (_, append) => append({type:'post',id,at:1000,urgency:'urgent',
    text:'Synthetic rollout FYI',ref:'fixture-rollout-reference',key:'stable-key',
    origin:{sessionID:'ses_origin',directory:'/original'}}));
  const batch = await f.bus.claim(); await f.bind(batch);
  const result = await f.bus.resolve({sessionID:'ses_child',event:'fixture-rollout-reference',
    route:'filed',text:'Recorded original milestone'}, {decisions:{}});
  assert.equal(result.event,id);
  await f.bus.finish(batch.id);
  assert.equal((await f.bus.rows()).find(r=>r.type==='result').event,id);
  const item=dispatchItems(batch.items)[0];
  assert.equal(item.action_handle,id);
  assert.equal(item.business_reference_nonrouting,'fixture-rollout-reference');
  assert.equal(item.id,undefined); assert.equal(item.ref,undefined);
});

test('ambiguous refs, out-of-batch refs/UUIDs and foreign dispatcher refuse without mutation', async t => {
  const f=await fixture(t); await f.post('one','duplicate'); await f.post('two','duplicate');
  const batch=await f.bus.claim(); await f.bind(batch); const outside=await f.post('outside','external-ref');
  const count=(await f.bus.rows()).length;
  for (const event of ['duplicate','external-ref',outside.id]) {
    await assert.rejects(f.bus.resolve({sessionID:'ses_child',event,route:'filed',text:'No'}, {decisions:{}}));
  }
  await assert.rejects(f.bus.resolve({sessionID:'ses_foreign',event:batch.items[0].id,route:'filed',text:'No'}, {decisions:{}}));
  assert.equal((await f.bus.rows()).length,count);
});

test('native terminal incomplete batch falls back once, finishes and cannot dispatch-storm same events', async t => {
  const f=await fixture(t), e=await f.post('question'); const b=await f.bus.claim(); await f.bind(b);
  await f.maintain(); assert.equal(await f.bus.active(),undefined);
  const s=state(await f.bus.rows()); assert.equal(s.events[0].result.effect,'no-effect-terminal-fallback');
  assert.equal(JSON.parse(await f.bus.inbox()).entries[0].id,e.id);
  assert.equal(await f.bus.claim(),undefined); await f.maintain();
  assert.equal((await f.bus.rows()).filter(r=>r.type==='finish').length,1);
  await f.post('new'); assert.ok(await f.bus.claim());
});

test('pre-prompt idle window cannot retire an unadmitted child', async t => {
  const f=await fixture(t); await f.post('question'); const b=await f.bus.claim(); await f.bus.bind(b.id,'ses_child','ses_chief');
  await f.maintain(); assert.equal((await f.bus.active()).id,b.id);
  assert.equal(state(await f.bus.rows()).events[0].result,undefined);
  f.setTime(1000+questionFallbackMs); f.ctx.session.context=async()=>[];
  await f.maintain(); assert.equal((await f.bus.active()).health,'prompt-admission-uncertain-needs-chief');
  f.ctx.session.context=async()=>[{type:'user',time:{created:1001}}, {type:'idle',time:{created:1002},outcome:'succeeded'}];
  await f.maintain(); assert.equal(await f.bus.active(),undefined);
});

test('active child stays owned until deadline, then one supported cancellation confirms idle before release', async t => {
  const f=await fixture(t); await f.post('question'); const b=await f.bus.claim(); await f.bind(b); f.setBusy(true);
  await f.maintain(); assert.equal(f.calls.length,0); assert.equal((await f.bus.active()).health,'active-within-deadline');
  f.setTime(1000+claimDeadlineMs); await f.maintain();
  assert.deepEqual(f.calls,[{sessionID:'ses_child',resume:false}]); assert.equal(await f.bus.active(),undefined);
  assert.equal(await f.bus.claim(),undefined);
});

test('uncertain cancellation never repeats or releases; stale question remains visible with provenance', async t => {
  const f=await fixture(t), e=await f.post('question'); const b=await f.bus.claim(); await f.bind(b);
  f.setBusy(true); f.setUncertain(true); f.setTime(1000+questionFallbackMs);
  await f.maintain(); await f.maintain(); assert.equal(f.calls.length,1);
  assert.equal((await f.bus.active()).health,'interrupt-uncertain-needs-chief');
  const inbox=JSON.parse(await f.bus.inbox()); assert.equal(inbox.entries[0].id,e.id);
  assert.equal(inbox.entries[0].needsReconciliation,true);
  assert.equal(inbox.entries[0].provenance.dispatcher,'ses_child');
});

test('native error/unbound uncertainty is not mistaken for idle or age-only reclaim', async t => {
  const f=await fixture(t); await f.post('question'); const b=await f.bus.claim();
  f.setTime(1000+questionFallbackMs); await f.maintain();
  assert.equal((await f.bus.active()).health,'unbound-uncertain-needs-chief');
  await f.bind(b); f.setUnavailable(true); await f.maintain();
  assert.equal((await f.bus.active()).health,'native-error-no-replay');
  assert.equal(f.calls.length,0); assert.equal(JSON.parse(await f.bus.inbox()).total,1);
});

test('expired foreign ownership is not cancelled, and uncertain result effects are never replayed', async t => {
  const f=await fixture(t), e=await f.post('question'); const b=await f.bus.claim(); await f.bind(b);
  f.ctx.session.get=async()=>({id:'ses_child',parentID:'ses_other',metadata:{heartbeatDispatcher:true}});
  f.setBusy(true); f.setTime(1000+questionFallbackMs); await f.maintain(); assert.equal(f.calls.length,0);
  assert.equal((await f.bus.active()).health,'expired-ownership-uncertain-needs-chief');
  f.setBusy(false);
  // Historical principal attempt predates chief-only creation. Preserve it; do
  // not manufacture a new outward attempt just to construct this recovery case.
  await f.bus.transaction(async(_,append)=>append({type:'result',event:e.id,route:'principal',text:'Question',effect:'uncertain-no-replay'}));
  await f.maintain(); assert.equal(await f.bus.active(),undefined);
  assert.equal(state(await f.bus.rows()).events[0].result.effect,'uncertain-no-replay');
  assert.equal(await f.bus.claim(),undefined);
});

test('full queue includes unresolved questions and preserves historical admitted-but-unclosed items for reconciliation', async t => {
  const f=await fixture(t); const e=await f.post('unclaimed'); f.setTime(1000+questionFallbackMs);
  assert.equal(JSON.parse(await f.bus.inbox()).entries[0].provenance.health,'unclaimed');
  const b=await f.bus.claim(); await f.bind(b);
  await f.bus.resolve({sessionID:'ses_child',event:e.id,route:'covered',text:'Policy',decision:'p',quote:'Policy'}, {decisions:{p:'Policy'}});
  await f.bus.deliver(e.id,async()=>{throw Error('native unknown');});
  assert.equal(JSON.parse(await f.bus.inbox()).entries[0].provenance.originalDisposition.route,'covered');
  await f.bus.transaction(async(_,append)=>append({type:'reply-outcome',event:e.id,status:'answer-admitted'}));
  assert.equal(JSON.parse(await f.bus.inbox()).total,1); // Historical outcome alone is not an explicit close.
});
