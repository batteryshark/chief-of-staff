// Origin-bound native adapter for existing Runway records and heartbeat eligibility.
// No daemon, queue, goal writes, prompt retries, or synthetic parent wake.
import {createHash} from 'node:crypto';
import {dispatchEligibility} from './dispatch-eligibility.mjs';

const hash = text => createHash('sha256').update(text).digest('hex');
const unwrap = value => value?.data ?? value;
const required = (ok, message) => { if (!ok) throw Error(message); };
const sameModel = (a, b) => a?.providerID === b.providerID && a?.id === b.id && a?.variant === b.variant;
const sameOrigin = (a, b) => ['sessionID','messageID','callID','directory'].every(k => a?.[k] === b?.[k]);

async function guard(deps, binding) {
  required(typeof deps.checkEligibility === 'function', 'Eligibility reader required');
  const state = await deps.checkEligibility(binding);
  required(state?.sessionID === binding.sessionID && state?.directory === binding.directory
    && state.held === false && state.archived === false, 'Held/archived/unknown/moved recipient');
}

function validate(task) {
  required(task?.id && /^msg_/.test(task.inputID ?? '') && typeof task.text === 'string' && task.text.trim(), 'Admission id/input/text required');
  required(/^ses_/.test(task.origin?.sessionID ?? '') && /^msg_/.test(task.origin?.messageID ?? '')
    && task.origin.callID && task.origin.directory?.startsWith('/'), 'Trusted exact caller origin required');
  required(task.agent && task.directory?.startsWith('/') && task.model?.providerID && task.model?.id
    && typeof task.model.variant === 'string' && task.model.variant, 'Explicit agent/selectable id/variant/location required');
}

async function verifyOrigin(deps, origin) {
  await guard(deps, origin);
  const message = unwrap(await deps.api('GET', `/api/session/${origin.sessionID}/message/${origin.messageID}`));
  required(message?.id === origin.messageID && message.type === 'assistant'
    && message.content?.some(p => p.type === 'tool' && p.id === origin.callID), 'Origin tool call not in native transcript');
}

async function verifyWorker(deps, task) {
  await guard(deps, {sessionID: task.sessionID, directory: task.directory});
  const worker = unwrap(await deps.api('GET', `/api/session/${task.sessionID}`));
  required(worker?.id === task.sessionID && worker.location?.directory === task.directory
    && worker.agent === task.agent && sameModel(worker.model, task.model), 'Worker selection/location differs');
  required(!worker.metadata?.openchamber?.goal && !worker.time?.archived, 'Goal-enabled/archived worker unsupported');
}

export async function createSelected(deps, task) {
  validate(task);
  task = {...task, textHash: hash(task.text)};
  required(typeof deps.save === 'function', 'Existing durable admission writer required');
  await verifyOrigin(deps, task.origin);
  const catalog = unwrap(await deps.api('GET', '/api/model'));
  const row = catalog.find(m => m.providerID === task.model.providerID && m.id === task.model.id);
  required(row?.enabled === true && row.variants?.some(v => (v.id ?? v) === task.model.variant), 'Exact enabled selectable model/variant unavailable');
  await deps.save({...task, state: 'creating'}, {expectedState: null});
  await verifyOrigin(deps, task.origin);
  // Native creation accepts selection even WITHOUT a prompt. Never normalize id.
  const worker = unwrap(await deps.api('POST', '/api/session', {
    title: task.title ?? task.id, agent: task.agent, model: task.model,
    location: {directory: task.directory},
  }));
  const created = {...task, origin: {...task.origin}, model: {...task.model}, sessionID: worker.id, state: 'created'};
  await deps.save(created, {expectedState: 'creating'}); // Owner CAS; preserve identity even if readback refuses.
  await verifyWorker(deps, created);
  return created;
}

export async function admit(deps, task) {
  validate(task);
  required(task.state === 'created' && /^ses_/.test(task.sessionID ?? ''), 'Only a fresh explicit admission can send; uncertain sends require reconciliation');
  await verifyOrigin(deps, task.origin);
  await verifyWorker(deps, task);
  const reserved = {...task, textHash: hash(task.text), state: 'uncertain'};
  await deps.save(reserved, {expectedState: 'created'}); // Owner CAS before effects, not a concurrency heuristic.
  // Re-read holds after persistence. No failed acknowledgement is automatically retried.
  await verifyOrigin(deps, task.origin);
  await verifyWorker(deps, task);
  const receipt = unwrap(await deps.api('POST', `/api/session/${task.sessionID}/prompt`, {
    id: task.inputID, text: task.text, delivery: 'queue',
  }));
  required(receipt?.id === task.inputID && receipt.sessionID === task.sessionID, 'Admission acknowledgement uncertain');
  const admitted = {...reserved, state: 'admitted'};
  await deps.save(admitted, {expectedState: 'uncertain'});
  return admitted;
}

export async function readTranscript(deps, sessionID) {
  const messages = []; let cursor;
  // Pagination, not completion polling. Incomplete history fails closed.
  for (let page = 0; page < 10; page++) {
    const query = new URLSearchParams({limit: '100', ...(cursor ? {cursor} : {order: 'asc'})});
    const response = await deps.api('GET', `/api/session/${sessionID}/message?${query}`);
    required(Array.isArray(response?.data), 'Native transcript unavailable');
    messages.push(...response.data);
    required(response.cursor && (response.cursor.next === null || typeof response.cursor.next === 'string'), 'Transcript completeness unknown');
    if (response.cursor.next === null) return messages;
    required(response.cursor.next !== cursor, 'Repeated transcript cursor');
    cursor = response.cursor.next;
  }
  throw Error('Transcript exceeds bounded complete read');
}

export function correlate(task, records) {
  const matches = records.flatMap((m, i) => m.id === task.inputID ? [i] : []);
  required(matches.length === 1, 'Exact input missing/duplicated; no newest-answer fallback');
  const input = records[matches[0]];
  required(input.type === 'user' && hash(input.text) === task.textHash, 'Exact input content differs');
  let answer;
  for (const message of records.slice(matches[0] + 1)) {
    required(!['user','synthetic','compaction','agent-switched','model-switched','location-switched'].includes(message.type), 'Intervening input/selection makes turn ambiguous');
    if (message.type === 'assistant') {
      required(message.agent === task.agent && sameModel(message.model, task.model), 'Executed agent/model differs');
      if (message.time?.completed) answer = message;
    }
    if (message.type === 'idle') {
      required(message.outcome === 'succeeded' && answer && !answer.error && answer.finish === 'stop', 'No successful terminal answer for exact input');
      return {origin: {...task.origin}, attemptID: task.id, sessionID: task.sessionID,
        inputID: task.inputID, assistantID: answer.id, idleID: message.id,
        model: {...answer.model}, text: answer.content.filter(p => p.type === 'text').map(p => p.text).join('')};
    }
  }
  throw Error('Exact input has no terminal idle yet');
}

export async function collect(deps, task, expectedOrigin) {
  required(task.state === 'admitted' && sameOrigin(task.origin, expectedOrigin), 'Wrong originating caller/turn/tool');
  await verifyOrigin(deps, expectedOrigin);
  await verifyWorker(deps, task);
  const result = correlate(task, await readTranscript(deps, task.sessionID));
  await verifyOrigin(deps, expectedOrigin);
  await verifyWorker(deps, task);
  await deps.save({...task, state: 'collected', result}, {expectedState: 'admitted'});
  // Return to the bound tool/owner only. No wake, no latest-turn synthetic message.
  return result;
}

// Existing plugin tool-context + native APIs; no listener, daemon or parent wake.
export function nativeDispatchAdvice(request, result, options) {
  if (options===undefined || request.action!=='prepare' || result.dispatch_allowed!==true || result.action!=='session.create') return result;
  required(result.attempt?.id,'Prepared admission identity missing');
  return {...result,action:'runway.dispatch',args:{attempt:result.attempt.id},transport:'native-exact-input',
    note:'Use runway request {action:"dispatch",attempt:<id>,prompt:<complete brief>}; do not use generic host returnResult.'};
}
export function validateDispatchRequest(request) {
  const allowed=request.action==='dispatch'?['action','attempt','prompt']:request.action==='collect-dispatch'?['action','attempt']:[];
  required(allowed.length && typeof request.attempt==='string' && request.attempt
    && Object.keys(request).every(k=>allowed.includes(k)),'Only attempt/prompt are agent inputs; no supplied origin/selection/policy');
}
export async function dispatchNative(ctx, context, request, invoke) {
  validateDispatchRequest(request);
  const options=ctx.options?.hostDispatch;
  required(options && typeof options==='object','Native dispatch disabled: operator bindings required');
  const timeout=options.completionTimeoutMs ?? 25000;
  required(Number.isInteger(timeout) && timeout>0 && timeout<=60000,'Bounded native completion timeout required');
  const call=async input=>{
    const value=await invoke({...input,format:'json'},{signal:context.signal});
    required(value && !value.error,'Runway dispatch record operation refused');
    return value;
  };
  const readAttempt=()=>call({action:'dispatch-get',attempt:request.attempt});
  const a=await readAttempt();
  const native=unwrap(await ctx.session.get({sessionID:context.sessionID}));
  const currentOrigin={sessionID:context.sessionID,messageID:context.messageID,callID:context.id,directory:native.location?.directory};
  required(currentOrigin.messageID && currentOrigin.callID && currentOrigin.directory===ctx.location.directory
    && a.task.directory===currentOrigin.directory,'Exact same-location native tool context required');
  const retrieving=request.action==='collect-dispatch';
  const origin=retrieving?a.host_dispatch?.origin:currentOrigin;
  required(origin && origin.sessionID===currentOrigin.sessionID && origin.directory===currentOrigin.directory,'Original owner must explicitly collect');
  const eligibility=dispatchEligibility(ctx,options,readAttempt,origin,context);
  const api=async(method,url,body)=>{
    const sid=/^\/api\/session\/(ses_[A-Za-z0-9]+)(?:\/|$)/.exec(url)?.[1];
    if(method==='GET' && url==='/api/model')return {data:unwrap(await ctx.model.list())};
    if(method==='POST' && url==='/api/session')return {data:unwrap(await ctx.session.create(body,{signal:context.signal}))};
    if(method==='GET' && sid && url===`/api/session/${sid}`)return {data:unwrap(await ctx.session.get({sessionID:sid}))};
    if(method==='GET' && sid && url.startsWith(`/api/session/${sid}/message`)) {
      const records=unwrap(await ctx.session.context({sessionID:sid}));
      required(Array.isArray(records) && records.length<=1000,'Complete bounded native context required');
      if(url.includes('/message/')) {
        const id=url.split('/message/')[1];
        const matches=records.filter(m=>m.id===id);required(matches.length===1,'Exact native tool message absent/ambiguous');
        return {data:matches[0]};
      }
      return {data:records,cursor:{next:null}};
    }
    if(method==='POST' && sid && url.endsWith('/prompt'))return {data:unwrap(await ctx.session.prompt({sessionID:sid,...body},{signal:context.signal}))};
    throw Error('Unsupported native dispatch operation');
  };
  const deps={api,checkEligibility:eligibility,save:(value,{expectedState})=>call({action:'dispatch-save',attempt:a.id,value,expected_state:expectedState})};
  let task;
  if(retrieving) {
    task=a.host_dispatch;
    required(task && ['admitted','collected'].includes(task.state),'Dispatch incomplete/uncertain; no automatic replay');
    await verifyOrigin(deps,origin);await verifyWorker(deps,task);
    if(task.state==='collected')return {status:'collected',result:task.result,retrievedBy:currentOrigin};
  } else {
    required(!a.host_dispatch && a.state==='admitted' && !a.session_id,'Fresh unbound admission required; never resend');
    const slash=a.model?.indexOf('/');required(slash>0,'Reserved exact provider/model required');
    task={id:a.id,inputID:a.message_id,text:request.prompt,title:a.job,origin,directory:a.task.directory,
      model:{providerID:a.model.slice(0,slash),id:a.model.slice(slash+1),variant:a.variant},agent:a.agent ?? options.workerAgent};
    task=await createSelected(deps,task);
    task=await admit(deps,task);
  }
  try {
    const signal=context.signal?AbortSignal.any([context.signal,AbortSignal.timeout(timeout)]):AbortSignal.timeout(timeout);
    await ctx.session.wait({sessionID:task.sessionID},{signal}); // Existing supported completion seam; one call.
    const result=await collect(deps,task,origin);
    return {status:'collected',result,...(retrieving?{retrievedBy:currentOrigin}:{})};
  } catch {
    // Keep the exact admission available to explicit owner collection, not resend.
    // A stopped tool may abort even this bookkeeping; original record still owns it.
    try {await invoke({action:'dispatch-incomplete',attempt:a.id,input_id:task.inputID,format:'json'},
      {signal:AbortSignal.timeout(5000)});} catch {}
    return {status:'incomplete',attemptID:a.id,sessionID:task.sessionID,origin,
      reason:'Native completion/history/eligibility incomplete; reconcile or explicitly collect this exact admission. Do not resend.'};
  }
}
