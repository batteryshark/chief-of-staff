// Passive source candidate. No permission.reply/assert/update, prompts, retries or grants.
import { observeDenial, permissionObservation, observePermissionRejection } from './denials.mjs';
import { denialLog } from './denial-log.mjs';

const callKey=e=>JSON.stringify([e.sessionID,e.messageID,e.id]);
const requestKey=(session,request)=>JSON.stringify([session,request]);
const safeID=(value,prefix)=>typeof value==='string' && new RegExp(`^${prefix}[A-Za-z0-9_-]{1,160}$`).test(value);

export async function setupObserver(ctx, options={}, dependencies={}) {
  // Disabled-by-default is inert even if options are incomplete. No file or native call.
  if (options.enabled!==true) return {enabled:false,async close(){},status:()=>({enabled:false})};
  if (options.candidateOnly!==true || options.directory!==ctx.location.directory || !Array.isArray(options.bindings))
    throw Error('Explicit candidate Location/bindings required');
  const bindings=new Map();
  for (const binding of options.bindings) {
    if (!safeID(binding.sessionID,'ses_') || typeof binding.agentID!=='string' || !binding.agentID
        || binding.compilation?.binding.location!==options.directory)
      throw Error('Exact session/agent/Location assignment required');
    const key=JSON.stringify([binding.sessionID,binding.agentID]);
    if (bindings.has(key)) throw Error('Duplicate observer binding');
    bindings.set(key,structuredClone(binding));
  }
  const sink=await (dependencies.openLog??denialLog)(options.logFile);
  const counts={observed:0,duplicates:0,diagnosticLoss:0,evictions:0,uncorrelatedRejects:0,streamEnded:0};
  const calls=new Map(),asks=new Map(),registrations=[],controller=new AbortController();
  const cap=256;let closed=false,stream,loggingAvailable=true;
  const diagnostic=code=>{ counts.diagnosticLoss++;try { dependencies.diagnostic?.(code); } catch {} };
  const retain=(map,key,value)=>{
    if (map.size>=cap && !map.has(key)) {map.delete(map.keys().next().value);counts.evictions++;}
    map.set(key,value);
  };
  const context=call=>bindings.get(JSON.stringify([call.sessionID,call.agent]))??{};
  const append=async record=>{
    if (!record || closed) return false;
    try {const result=await sink.append(record);if(result.status==='duplicate') counts.duplicates++;else counts.observed++;loggingAvailable=true;return true;}
    catch {loggingAvailable=false;diagnostic('denial-log-append-failed');return false;}
  };
  const onBefore=event=>{
    if (closed || !safeID(event.sessionID,'ses_') || !safeID(event.messageID,'msg_') || !safeID(event.id,'call_')) return;
    // Do not retain input/commands/env/cause. Known context uses explicit immutable setup binding.
    retain(calls,callKey(event),{sessionID:event.sessionID,agent:event.agent,tool:event.tool,messageID:event.messageID,id:event.id});
  };
  const onAfter=async event=>{
    if (closed) return;
    try {await append(observeDenial(event,context(event)));}
    catch {diagnostic('denial-observation-failed');}
    finally {calls.delete(callKey(event));}
  };
  const onEvent=async event=>{
    if (closed) return;
    const payload=event?.data;
    if (!payload || !safeID(payload.sessionID,'ses_')) return;
    if (event.type==='permission.asked') {
      if (!safeID(payload.id,'per_')) return;
      const source=payload.source;
      const call=source?.type==='tool'?calls.get(callKey({sessionID:payload.sessionID,messageID:source.messageID,id:source.id})):null;
      // Public stream is global. Only local native-call correlation OR exact native
      // event Location admits an observation; no session-name/role/location guessing.
      if (!call && event.location?.directory!==options.directory) return;
      const observation=permissionObservation(payload,call?context(call):{},call);
      retain(asks,requestKey(payload.sessionID,payload.id),observation);
    } else if (event.type==='permission.replied') {
      const key=requestKey(payload.sessionID,payload.requestID),asked=asks.get(key);
      if (!asked && event.location?.directory!==options.directory) return;
      if (payload.reply==='reject') {
        if (!asked) counts.uncorrelatedRejects++;
        // Preserve bounded sanitized attribution on failed persistence. Only a
        // separately delivered event can try again; no automatic retry is added.
        if (!await append(observePermissionRejection(event,asked))) return;
      }
      if (asked?.source.call) calls.delete(callKey({sessionID:asked.source.session,messageID:asked.source.message,id:asked.source.call}));
      asks.delete(key);
    }
  };
  const close=async()=>{
    if (closed) return;closed=true;controller.abort();
    for (const r of registrations) {try {await r.dispose();} catch {diagnostic('denial-hook-dispose-failed');}}
    await stream;
    calls.clear();asks.clear();try {await sink.close();} catch {diagnostic('denial-log-close-failed');}
  };
  try {
    registrations.push(await ctx.tool.hook('execute.before',onBefore));
    registrations.push(await ctx.tool.hook('execute.after',onAfter));
    stream=(async()=>{
      try {
        for await (const event of ctx.event.subscribe({signal:controller.signal})) {
          try {await onEvent(event);} catch {diagnostic('denial-event-observation-failed');}
        }
        if (!closed) {counts.streamEnded++;diagnostic('denial-event-stream-ended');}
      } catch {if (!closed) diagnostic('denial-event-stream-failed');}
    })();
  } catch {await close();throw Error('Passive denial observer setup failed');}
  return {enabled:true,close,status:()=>({enabled:!closed,loggingAvailable:!closed&&loggingAvailable,...counts,pendingCalls:calls.size,pendingRequests:asks.size})};
}

export default {id:'chief-access-denials-candidate',async setup(ctx) {
  const observer=await setupObserver(ctx,ctx.options);
  return ()=>observer.close();
}};
