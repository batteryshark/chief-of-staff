// OPTIONAL source-only native desk adapter. No HTTP/auth discovery/return watcher.
import fs from 'node:fs';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {bridge} from './bridge.mjs';
import {boundary} from './boundary.mjs';

const hash = x => createHash('sha256').update(x).digest('hex');
export const descriptorHash = t => hash(JSON.stringify({description:t.description,input:t.input,options:t.options}));
const object = properties => ({type:'object',properties,required:Object.keys(properties),additionalProperties:false});
const string = {type:'string',minLength:1,maxLength:1000};
const integer = {type:'integer',minimum:0};
const reportSchema = object({project:string,id:string,source_revision:integer,observed:string,
  landed:{type:'string',maxLength:10000},next:{type:'string',maxLength:10000},
  your_part:{type:['string','null'],maxLength:10000},state:{enum:['active','paused','waiting']},
  request:{type:'string',maxLength:10000},rule:{type:'string',maxLength:10000}});
const schemas = {
  desk_report:object({report:reportSchema}), desk_inbox:object({inputId:string}),
  desk_project_sync:object({receiptId:integer}),
  desk_propose:object({receiptId:integer,ruleId:string,typedChoice:{enum:['apply-exact-recorded-rule']}}),
  desk_decision:object({project:string,sourceReceipt:integer,itemKey:string,expectedRevision:integer,
    state:{enum:['open','closed','revoked']},decisionText:string}),
};
const toolRoles = {lead:['desk_report'],desk:['desk_inbox','desk_project_sync','desk_propose'],chief:['desk_decision']};
export function role(c, agent) {
  if (agent === c.desk_agent) return 'desk';
  if (agent === c.chief_agent) return 'chief';
  if (Object.values(c.projects).some(p=>p.lead_agent === agent)) return 'lead';
}
export function filter(c, event, strict=false) {
  const r = role(c, event.agent), permitted = new Set(toolRoles[r] || []);
  for (const name of Object.keys(event.tools)) {
    if (strict || r === 'desk' || r === 'lead' ? !permitted.has(name) : name.startsWith('desk_') && !permitted.has(name)) delete event.tools[name];
  }
}
function exact(raw, schema) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) || Object.keys(raw).sort().join() !== schema.required.slice().sort().join()) throw Error('unexpected tool arguments');
  for (const [k,s] of Object.entries(schema.properties)) {
    const v=raw[k];
    if (s.type === 'object') exact(v,s);
    else if (s.type === 'integer' && (!Number.isSafeInteger(v) || v<0)) throw Error('invalid integer');
    else if (s.type === 'string' && (typeof v!=='string' || v.length>(s.maxLength||1000) || v.length<(s.minLength||0))) throw Error('invalid bounded string');
    else if (Array.isArray(s.type) && !(v===null || typeof v==='string' && v.length<=s.maxLength)) throw Error('invalid nullable string');
    if (s.enum && !s.enum.includes(v)) throw Error('invalid typed choice');
  }
}
export function makePlugin(options, dependencies={}) {
  return {id:'chief-desk-native', async setup(ctx) {
    if (options.enabled !== true) return;
    const home=fs.realpathSync(options.home);
    if (home!==options.home) throw Error('canonical home required');
    const configPath=path.join(home,'desk/native-host.json');
    const load=()=>{
      dependencies.fixture?.check();
      const c=dependencies.fixture ? dependencies.fixture.config() : JSON.parse(fs.readFileSync(configPath,'utf8'));
      if (c.version!==1 || c.enabled!==true || c.desk_agent===c.chief_agent) throw Error('native adapter disabled/invalid');
      return c;
    };
    // Test clocks/budgets are host dependencies, never model arguments/config.
    const fence=boundary(dependencies.budget);
    if (dependencies.fixture) {
      dependencies.fixture.signal?.addEventListener('abort',()=>fence.stop(),{once:true});
      if (dependencies.fixture.signal?.aborted) fence.stop();
    }
    const rawInvoke=dependencies.invoke || bridge({home,python:options.python});
    // Per serialized turn, NOT a persistent readiness/file-seal authority flag.
    let fixtureCaller=false;
    let probing;
    const invoke=(...args)=>fence.observe(()=>{
      if (dependencies.fixture) {
        dependencies.fixture.check();
        if (!fixtureCaller) throw Error('fixture native caller not verified for this turn');
      }
      return Promise.resolve(rawInvoke(...args)).then(value=>{fence.check();dependencies.fixture?.observed?.('bridge',args[0],args[1],value);return value;});
    },dependencies.budget?.bridgeMs || 5000);
    const rpc=(method,input)=>fence.observe(()=>{
      dependencies.fixture?.check();
      return Promise.resolve(ctx.session[method](input)).then(value=>{fence.check();dependencies.fixture?.observed?.('native',method,input,value);return value;});
    });
    const session=async id=>{
      const s=await rpc('get',{sessionID:id});
       if (s.id!==id || s.time?.archived || !path.isAbsolute(s.location?.directory||'')) throw Error('native session unavailable');
       dependencies.fixture?.native?.(s);
      return {...s,location:{...s.location,directory:fs.realpathSync(s.location.directory)}};
    };
    const pointer=name=>{
      const p=JSON.parse(fs.readFileSync(path.join(home,name+'.json'),'utf8'));
      if (p.directory!==home || !/^ses_[A-Za-z0-9]+$/.test(p.session)) throw Error('invalid native pointer');
      return p.session;
    };
    const context=c=>({sessionID:c.sessionID,agent:c.agent,messageID:c.messageID,id:c.id});
    async function caller(c, needed) {
      fixtureCaller=false;
           dependencies.fixture?.ready();
           dependencies.fixture?.start?.();
      const cfg=load();
      if (role(cfg,c.agent)!==needed) throw Error('wrong native role');
      const actual=await session(c.sessionID);
      dependencies.fixture?.caller(c,actual);
      if (actual.agent!==c.agent || !c.messageID || !c.id) throw Error('native caller mismatch');
      if (needed==='chief' || needed==='desk') {
        if (actual.location.directory!==home || actual.id!==pointer(needed)) throw Error('native owner rotated/moved');
      }
      fixtureCaller=true;
      // Host-only closure: model JSON cannot request/mint this verified hook or
      // boundary entry receipt. Always uses the unchanged registered caller c.
      if(dependencies.fixture?.verified) await dependencies.fixture.verified(c,actual,{
        list:()=>ctx.tool.list(),observe:fn=>fence.observe(fn),
        probe:async(t,args,actualContext)=>{
          if(probing || actualContext!==c) throw Error('private probe scope mismatch');
          const token={call:context(c),tool:t.id,args:JSON.stringify(args),entered:false};probing=token;
          try {await fence.observe(()=>t.execute(args,c));return false;}
          catch(error) {fence.check();return token.entered;}
          finally {probing=undefined;}
        },
      });
      return actual;
    }
    async function evidence(value) {
      return {sender:await session(value.auth.sender),desk:await session(pointer('desk')),chief:await session(pointer('chief'))};
    }
    async function active(target,id,type,body) {
      const records=await rpc('context',{sessionID:target});
      if (!Array.isArray(records)) return null;
      const hits=records.filter(r=>r.id===id && r.type===type && r.text===body);
      return hits.length===1 ? hits[0] : null; // compacted/notfound is NOT nonadmission
    }

    // Transform captures a fixed managed descriptor BEFORE wrapping raw tools.
    // On every invocation check current registry executor identity and source pin.
    let managed;
    const tickets=new Map(); // private one-use capabilities, never ToolContext fields
    function pinned(t,cfg) {
      const pin=cfg.knowledge;
      if (!pin || !path.isAbsolute(pin.source) || hash(fs.readFileSync(pin.source))!==pin.sha256
          || t.id!=='openchamber_knowledge' || t.disabled===true || typeof t.execute!=='function'
          || t.options?.codemode!==false || descriptorHash(t)!==pin.descriptor_sha256) throw Error('managed Knowledge unavailable/replaced');
    }
    async function knowledge(action,parameters,c) {
      const cfg=load(), current=(await fence.observe(()=>ctx.tool.list())).find(t=>t.id==='openchamber_knowledge');
      if (!current || !managed) throw Error('managed executor missing');
      pinned(current,cfg);
      await caller(c,'desk');
      const ticket=randomUUID(), capability={input:{action,parameters},context:context(c),entered:false};
      tickets.set(ticket,capability);
      let raw;
      try {
        // ctx.tool.list may return fresh bridge-wrapped functions. Do NOT use
        // cross-bridge function equality. Require entry into OUR registered guard.
        raw=await fence.observe(()=>current.execute({action,parameters,__deskHostTicket:ticket},c));
        if (!capability.entered) throw Error('managed guard replaced/bypassed');
      } finally {tickets.delete(ticket);}
      const envelope=JSON.parse(raw.content);
      if (envelope.schemaVersion!==1 || envelope.ok!==true || envelope.action!==action || !envelope.data) throw Error('managed Knowledge error; reconcile, never blind retry');
      dependencies.fixture?.observed?.('managed',action,{call:context(c),parameters},envelope.data);
      return envelope.data;
    }

    async function send(action) {
      if (!['receipt','escalation','routine-relay','decision-relay','projection-wake'].includes(action.kind)) return;
      const e=await evidence(action);
      const claimed=await invoke('claim_action',{action_id:action.id,...e});
      if (!claimed.send) return;
      // Claim has made this action uncertain durably before admission. Never replay
      // on any exception, 409, cancellation, response loss or persistence failure.
      await invoke('check_send',{action_id:action.id,...await evidence(action)});
      ownedSessions.add(claimed.target);
      const admitted=await rpc('synthetic',{sessionID:claimed.target,id:claimed.native_id,
        text:claimed.body,delivery:'queue',resume:true,metadata:{deskAction:claimed.id}});
      await invoke('action_admitted',{action_id:claimed.id,evidence:admitted});
    }
    async function syncAction(action,c) {
      const e=await evidence(action);
      await invoke('inspect_action',{action_id:action.id,...e});
      const directory=action.kind==='overview-note' ? home : action.auth.path;
      // Host-only full list: no unrelated item content is returned to the model.
      const listing=await knowledge('knowledge.list',{directory},c);
      const intent=await invoke('note_prepare',{action_id:action.id,listing,...e});
      if (!intent.send) {
        if (intent.state==='uncertain') return invoke('note_reconcile',{action_id:action.id,listing});
        return {state:intent.state,reason:intent.reason};
      }
      await invoke('check_send',{action_id:action.id,...await evidence(action)});
      const parameters={directory,kind:'note',body:intent.proposed};
      if (intent.note_id) Object.assign(parameters,{id:intent.note_id,expected:intent.expected});
      const saved=await knowledge('knowledge.save',parameters,c);
      await invoke('note_returned',{action_id:action.id,saved});
      const readback=await knowledge('knowledge.list',{directory},c);
      return invoke('note_reconcile',{action_id:action.id,listing:readback});
    }
    async function inbox(inputId,c) {
      await caller(c,'desk');
      const value=await invoke('input',{input_id:inputId});
      const e=await evidence(value);
      if (e.desk.id!==c.sessionID) throw Error('not owned desk input');
      const record=await active(e.desk.id,inputId,'user',value.body);
      if (!record) return {state:'uncertain',reason:'exact active input unavailable; no outgoing receipt'};
      const filed=await invoke('file_input',{input_id:inputId,record,...e});
      if (filed.duplicate) return {receiptId:filed.seq,duplicate:true,send:false};
      // Each action persists/finishes independently. Projection failure cannot eat
      // the filing receipt; escalation failure cannot send a second ACK.
      const status=[];
      for (const a of (filed.actions || []).slice(0,4)) {
        try {
          if (a.kind.endsWith('-note')) await syncAction(a,c); else await send(a);
          status.push({kind:a.kind,state:'inspect-owned-action'});
        } catch { status.push({kind:a.kind,state:'pending/uncertain'}); }
      }
      if (dependencies.fixture) await invoke('smoke_state',{input_id:inputId});
      return {receiptId:filed.seq,filed:true,approval:false,actions:status};
    }
    const handlers={
      desk_report:async ({report},c)=>{
        const sender=await caller(c,'lead'), desk=await session(pointer('desk'));
        const value=await invoke('prepare_input',{report,sender,desk,call:context(c)});
        if (!value.send) return {inputId:value.id,state:value.state,send:false};
        const claimed=await invoke('claim_input',{input_id:value.id,sender:await session(c.sessionID),desk:await session(pointer('desk'))});
        if (!claimed.send) return {inputId:value.id,state:claimed.state,send:false};
        ownedSessions.add(claimed.auth.sender);ownedSessions.add(claimed.auth.target);
        const admitted=await rpc('prompt',{sessionID:claimed.auth.target,id:claimed.id,
          text:claimed.body,metadata:{deskInput:claimed.id},delivery:'queue',resume:true});
        await invoke('admit_input',{input_id:claimed.id,admission:admitted});
        return {inputId:claimed.id,state:'admitted',executionProven:false};
      },
      desk_inbox:async ({inputId},c)=>inbox(inputId,c),
      desk_project_sync:async ({receiptId},c)=>{
        await caller(c,'desk');
        const actions=await invoke('actions',{seq:receiptId}), result=[];
        for (const a of actions.filter(a=>a.kind.endsWith('-note')).slice(0,4)) {
          try { const n=await syncAction(a,c); result.push({kind:a.kind,state:n.state,pendingLatest:n.pending_latest}); }
          catch { result.push({kind:a.kind,state:'pending/uncertain'}); }
        }
        return {receiptId,projections:result};
      },
      desk_propose:async ({receiptId,ruleId,typedChoice},c)=>{
        await caller(c,'desk');
        const actions=await invoke('actions',{seq:receiptId});
        if (!actions.length) throw Error('no owned verified receipt');
        const a=await invoke('propose',{seq:receiptId,rule_id:ruleId,choice:typedChoice,...await evidence(actions[0])});
        await send(a);
        return {receiptId,actionId:a.id,approval:false};
      },
      desk_decision:async (args,c)=>{
        const actual=await caller(c,'chief');
        const actions=await invoke('actions',{seq:args.sourceReceipt});
        if (!actions.length || actions[0].auth.project!==args.project) throw Error('wrong project/source');
        const e=await evidence(actions[0]);
        const value=await invoke('decision',{args,caller:actual,sender:e.sender,desk:e.desk,call:context(c)});
        try { await send(value.action); } catch { /* durable pending/uncertain action, no retry */ }
        try { await send(value.wake); } catch { /* pending projection wake is independent */ }
        return {revision:value.decision.revision,principalApproval:false,relay:'inspect-owned-action',projection:'pending'};
      },
    };
    // One operation at a time, at most one waiting event notification (no queue
    // growth/process explosion). Concurrent model invocations refuse, not enqueue.
    let busy=false;
    async function serial(fn,signal) {
      if (busy || fence.stopped || fence.unresolved) throw Error('native adapter busy/stopped/unresolved');
      busy=true;fixtureCaller=false;
      try { return await fence.run(fn,signal); } finally { fixtureCaller=false;busy=false; }
    }
    await serial(async()=>{
    for (const kind of ['context','generate','compaction']) await fence.observe(()=>ctx.session.hook(kind,event=>{
      try {
        dependencies.fixture?.metadata?.(Object.values(event.tools));
        if (dependencies.fixture?.acceptsAgent?.(event.agent)===false) {for (const name of Object.keys(event.tools)) delete event.tools[name];return;}
         filter(load(),event,!!dependencies.fixture);
         dependencies.fixture?.catalog?.(kind,event);
      }
      catch (error) { for (const name of Object.keys(event.tools)) delete event.tools[name]; throw error; }
    }));
    await fence.observe(()=>ctx.permission.hook('evaluate',event=>{
      let r;
      try { r=role(load(),event.agent); }
      catch (error) { if (dependencies.fixture) {event.effect='deny';event.message='fixture pin/scope unavailable';} throw error; }
      if (dependencies.fixture?.acceptsAgent?.(event.agent)===false || (dependencies.fixture || r==='desk' || r==='lead') && !toolRoles[r]?.includes(event.action)) {
        event.effect='deny';event.message='native desk role has only typed guarded tools';
      }
    }));
    await fence.observe(()=>ctx.tool.transform(editor=>{
      fence.check(); // a delayed transform registration cannot install new work
      const cfg=load(); managed=undefined;
      dependencies.fixture?.metadata?.(editor.list());
      for (const t of editor.list()) {
        const execute=t.execute;
        const wrapper=async (raw,c)=>{
          dependencies.fixture?.check();
          if (t.id==='openchamber_knowledge' && typeof raw?.__deskHostTicket==='string') {
            const capability=tickets.get(raw.__deskHostTicket);
            if (!capability || JSON.stringify(capability.context)!==JSON.stringify(context(c))) throw Error('invalid host capability/caller');
            tickets.delete(raw.__deskHostTicket);capability.entered=true;
            await caller(c,'desk');
            return fence.observe(()=>{dependencies.fixture?.check();return execute(capability.input,c);}); // unchanged actual caller
          }
          const r=role(load(),c.agent);
          if (dependencies.fixture || r==='desk' || r==='lead') {
            if(probing && probing.tool===t.id && probing.args===JSON.stringify(raw) && JSON.stringify(probing.call)===JSON.stringify(context(c))) probing.entered=true;
            throw Error('generic executor denied for native desk role');
          }
          return execute(raw,c);
        };
        if (t.id==='openchamber_knowledge') {
          if (!dependencies.fixture) pinned(t,cfg);
          managed={wrapper}; // pending fixture capture grants NO invocation authority
        }
        if (typeof execute==='function') editor.update(t.id,v=>{v.execute=wrapper;});
      }
      for (const [name,input] of Object.entries(schemas)) editor.add({name,input,options:{codemode:false},
        description:'Optional guarded native desk action: '+name+'; no principal approval or arbitrary send.',
        execute:async (raw,c)=>serial(async ()=>{
          if (dependencies.fixture?.acceptsAgent?.(c.agent)===false) throw Error('fixture role/location denied');
          dependencies.fixture?.capture?.(name,c); // host-private actual registered invocation, never a model ticket
          dependencies.fixture?.ready();
          exact(raw,input); const r=role(load(),c.agent);
          if (!toolRoles[r]?.includes(name)) throw Error('native role denied');
           const result=await handlers[name](raw,c);
           dependencies.fixture?.observed?.('registered-tool',name,{call:context(c),args:raw},result);
           return {content:JSON.stringify(result)};
        },c.signal)});
    }));
    // Supported list, metadata ONLY; descriptor may not yet be registered.
    if(dependencies.fixture?.metadata && ctx.tool.list) dependencies.fixture.metadata(await fence.observe(()=>ctx.tool.list()));
    }).catch(()=>fence.stop());
    // Production recovery is bounded exact-read-only. Never dispatch planned or uncertain
    // actions automatically on restart. A record's absence does not authorize replay.
    const ownedSessions=new Set();
    async function reconcile() {
      // Fixture recovery is deliberately deferred, even after a verified typed call.
      // Future controllers must use guarded real native operations, never file seals.
      if (dependencies.fixture) throw Error('fixture automatic reconciliation disabled');
      const pending=await invoke('pending');
      ownedSessions.clear();
      for (const a of pending.actions) if (a.target) ownedSessions.add(a.target);
      for (const value of pending.inputs) {ownedSessions.add(value.auth.target);ownedSessions.add(value.auth.sender);}
      for (const a of pending.actions.slice(0,4)) {
        if (!['receipt','escalation','routine-relay','decision-relay','projection-wake'].includes(a.kind)) continue;
        try {
          const record=await active(a.target,a.native_id,'synthetic',a.body);
          if (record) await invoke('action_admitted',{action_id:a.id,evidence:record,inbox:false});
        } catch { /* uncertainty remains durable */ }
      }
      for (const value of pending.inputs.slice(0,4)) {
        if (!['admitted','uncertain'].includes(value.state)) continue;
        try {
          const e=await evidence(value);
          const record=await active(value.auth.target,value.id,'user',value.body);
          if (record) await invoke('file_input',{input_id:value.id,record,...e});
        } catch { /* moved/revoked/missing remains pending; no outgoing ACK */ }
      }
    }
    // Failed/abandoned startup is pending, not permission for new work.
    if (!dependencies.fixture) await serial(reconcile).catch(()=>{});
     const controller=new AbortController();
     dependencies.fixture?.signal?.addEventListener('abort',()=>controller.abort(),{once:true});
     if(dependencies.fixture?.signal?.aborted) controller.abort();
    let eventsEnded=false;
    const events=(async ()=>{
      try {
        if (fence.stopped) return;
        for await (const event of ctx.event.subscribe({signal:controller.signal})) {
           if (controller.signal.aborted || fence.stopped) break;
           // Fixture evidence ONLY, never reconciliation/bridge/action replay.
           if(dependencies.fixture?.watches?.(event)) {
             if(busy) dependencies.fixture.observed('unknown','event-during-turn',{},{});
             else {
               await serial(async()=>{
                 const id=event.data.sessionID;
                 await session(id);await rpc('context',{sessionID:id});
               }).catch(()=>{dependencies.fixture.observed('unknown','native-evidence-read-failed',{},{});});
               await dependencies.fixture.finish?.();
             }
           }
          if (event.type==='server.connected' ||
              ['session.execution.succeeded','session.execution.failed','session.execution.interrupted'].includes(event.type) && ownedSessions.has(event.data?.sessionID)) {
            if (!busy && !dependencies.fixture) await serial(reconcile).catch(()=>{});
          }
        }
      } catch { /* no daemon/reconnect/poll loop: operator reconcile on reload */ }
       finally {eventsEnded=true;dependencies.fixture?.ended?.();}
    })();
    // Do not await a plugin-scoped RPC/event iterator forever or claim quiescence.
    // A stuck underlying RPC keeps its slot until settlement, even after cleanup.
    return async ()=>{fence.stop();controller.abort();return {unresolved:fence.unresolved,quiesced:!busy && eventsEnded && fence.unresolved===0};};
  }};
}
