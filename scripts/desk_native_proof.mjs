// STAGED ONLY. Read-only observer for a later explicitly authorized native driver.
// No SDK boot/discovery, HTTP, credentials, session creation/prompt or model calls.
// Receives the existing supported ctx from the later reviewed host harness.
import fs from 'node:fs';
import {boundary} from '../hosts/desk-native/boundary.mjs';
const observers=new WeakMap(); // retain unresolved slots across repeated observations

export function validateManifest(manifest) {
  if (manifest.version!==1 || manifest.authorization!=='separately-authorized-throwaway-proof'
      || !Array.isArray(manifest.sessions) || manifest.sessions.length<1 || manifest.sessions.length>5) throw Error('owned proof manifest required');
  const ids=new Set();
  for (const s of manifest.sessions) {
    if (!/^ses_[A-Za-z0-9]+$/.test(s.sessionID) || ids.has(s.sessionID)
        || !s.agent || !s.projectID || fs.realpathSync(s.directory)!==s.directory
        || !Array.isArray(s.inputs) || s.inputs.length>16 || !Array.isArray(s.calls) || s.calls.length>16) throw Error('invalid fixed proof scope');
    ids.add(s.sessionID);
    for (const r of s.inputs) if (!/^msg_/.test(r.id) || !['user','synthetic'].includes(r.type)
        || typeof r.text!=='string' || r.text.length>60000) throw Error('invalid exact owned input');
    for (const c of s.calls) if (!/^msg_/.test(c.messageID) || !c.id || !c.name?.startsWith('desk_')) throw Error('invalid actual tool call correlation');
  }
}

export async function observeOwnedProof(ctx, manifest, {signal,budget}={}) {
  validateManifest(manifest);
  let owner=observers.get(ctx);
  if (!owner) {owner={fence:boundary(budget),busy:false};observers.set(ctx,owner);}
  if (owner.busy) throw Error('proof observer busy');
  owner.busy=true;
  const deadline=AbortSignal.timeout(budget?.turnMs || 60000), local=new AbortController();
  const bound=AbortSignal.any([signal,deadline,local.signal].filter(Boolean));
  const events=[];
  const watch=(async()=>{
    try {
      for await (const e of ctx.event.subscribe({signal:bound})) {
        if (!bound.aborted && manifest.sessions.some(s=>s.sessionID===e.data?.sessionID) && events.length<128)
          events.push({type:e.type,sessionID:e.data.sessionID});
      }
    } catch { /* read failure is reported by exact snapshots, not replay permission */ }
  })();
  try { return await owner.fence.run(async()=>{
    const result=[];
    for (const s of manifest.sessions) {
      const info=await owner.fence.observe(()=>ctx.session.get({sessionID:s.sessionID}));
      if (info.id!==s.sessionID || info.agent!==s.agent || info.projectID!==s.projectID
          || info.location?.directory!==s.directory || info.time?.archived) throw Error('actual native proof identity drift');
      const records=await owner.fence.observe(()=>ctx.session.context({sessionID:s.sessionID}));
      const inputs=s.inputs.map(expected=>({id:expected.id,
        matched:records.filter(r=>r.id===expected.id && r.type===expected.type && r.text===expected.text).length===1}));
      const calls=s.calls.map(expected=>{
        const message=records.find(r=>r.id===expected.messageID && r.type==='assistant');
        const call=message?.content?.find(c=>c.type==='tool' && c.id===expected.id && c.name===expected.name);
        return {messageID:expected.messageID,id:expected.id,name:expected.name,state:call?.state?.status || 'unavailable'};
      });
      result.push({sessionID:s.sessionID,inputs,calls,outcome:info.outcome || 'unknown'});
    }
    return {source:'actual-native-read-only-observer',sessions:result,events,
      nativeInputsMatched:result.every(s=>s.inputs.every(i=>i.matched)),
      acceptance:false,limits:'Active context only; no producer attestation, tool catalog denial, Note ownership, UI refresh, adoption or human-read proof by this observer alone.'};
  },bound); } finally {local.abort();owner.busy=false;}
}
