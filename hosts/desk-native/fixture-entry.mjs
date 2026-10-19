// Private fixture ONLY. Default export matches installed Promise-plugin setup.
// No automatic activation, bootstrap IDs, session creation, HTTP or auth.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {makePlugin} from './index.mjs';
import {agents,pendingConfig} from './fixture-config.mjs';
import {fileURLToPath} from 'node:url';
import {fixtureAssets} from './fixture-assets.mjs';
import {observer} from './fixture-observer.mjs';
import {validateAck,benignReport} from './fixture-operator.mjs';
import {validateSmoke} from './fixture-evidence.mjs';

const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
// Process-scoped tombstones deliberately survive new ctx / module entry instances.
// This is not a cross-process RPC cancellation mechanism. Never reload to clear it.
const key=Symbol.for('chief-desk-private-fixture-leases-v1');
const leases=globalThis[key] ||= new Map();
function privatePath(p,directory=false) {
  if (!path.isAbsolute(p) || fs.realpathSync(p)!==p) throw Error('canonical nonlinked fixture path required');
  const s=fs.lstatSync(p);
  if (s.isSymbolicLink() || s.uid!==process.getuid() || (s.mode&0o077) ||
      (directory ? !s.isDirectory() : !s.isFile() || s.nlink!==1)) throw Error('private owned fixture path required');
  return s;
}
function parents(p) {
  for (let d=p;;d=path.dirname(d)) {
    if (fs.existsSync(path.join(d,'.git'))) throw Error('fixture must be outside existing git roots');
    if (fs.lstatSync(d).isSymbolicLink()) throw Error('linked ancestor refused');
    if (path.dirname(d)===d) break;
  }
}
// Installed ConfigDiscovery (CLI 120709554+) considers these JSON/JSONC names
// and .opencode directory layers at each ancestor. ConfigAgentPlugin scans
// {agent,agents}/**/*.md and {mode,modes}/*.md; PluginSourceDirectory reads
// plugin/plugins children (including links). Compatibility discovers .agents
// and .claude too. Reject definition containers wholesale, without following links.
// This is fixture-LOCAL only: ancestors/global/managed/explicit/inline config are
// trusted operator assumptions, not attested by the one expected config file.
function discovery(root) {
  const present=p=>{
    try {return fs.lstatSync(p);} catch(error) {if(error.code==='ENOENT') return;throw error;}
  };
  const absent=p=>{if(present(p)) throw Error('unexpected fixture native discovery input');};
  for (const base of ['', 'home', 'lead-a', 'lead-b', 'fixture-plugin']) {
    const dir=path.join(root,base);
    for (const name of ['opencode.json','opencode.jsonc','.agents','.claude']) absent(path.join(dir,name));
    const layer=path.join(dir,'.opencode');
    // Check the container BEFORE any child access: never traverse an unknown link.
    if (present(layer)) {
      privatePath(layer,true);
      for (const name of ['opencode.json','opencode.jsonc','agent','agents','mode','modes',
        'plugin','plugins','command','commands','skill','skills']) {
        if (base==='' && name==='opencode.json') continue;
        absent(path.join(layer,name));
      }
    }
  }
}
export function preflight(options,location) {
  if (!options || Object.keys(options).sort().join()!=='enabled,python,root' || options.enabled!==true) throw Error('exact fixture options required');
  const {root,python}=options;
  privatePath(root,true);parents(root);
  for (const d of ['home','lead-a','lead-b','fixture-plugin','.opencode','home/desk']) privatePath(path.join(root,d),true);
  discovery(root);
  if (!['home','lead-a','lead-b'].some(d=>path.join(root,d)===location?.directory)) throw Error('fixture location refused');
  if (!path.isAbsolute(python) || fs.realpathSync(python)!==python || !fs.statSync(python).isFile() || (fs.statSync(python).mode&0o022)) throw Error('safe explicit Python required');
  fs.accessSync(python,fs.constants.X_OK);
  const pins=new Map();
  const pin=p=>{privatePath(p);const bytes=fs.readFileSync(p);pins.set(p,digest(bytes));return bytes;};
  const read=relative=>JSON.parse(pin(path.join(root,relative)));
  const config=read('.opencode/opencode.json');
  const expected=pendingConfig(root,python);
  expected.plugins[0].options.enabled=true;
  if (JSON.stringify(config)!==JSON.stringify(expected)) throw Error('exact dedicated fixture config required');
  const pkg=read('fixture-plugin/package.json');
  if (JSON.stringify(pkg)!==JSON.stringify(JSON.parse(fs.readFileSync(new URL('./fixture-package.json',import.meta.url))))) throw Error('private fixture package mismatch');
  // Inventory is not authority: trusted review must approve these hashes before load.
  // Every file must be pinned; no arbitrary path supplied by a model or metadata.
  const inventory=read('fixture-plugin/fixture-source.json');
   const files=fixtureAssets;
  if (Object.keys(inventory).sort().join()!==files.slice().sort().join()) throw Error('exact fixture source inventory required');
  for (const f of files) {
    const p=path.join(root,'fixture-plugin',f);
    // All intermediate package directories are private and nonlinked too.
    for (let d=path.dirname(p);d!==path.join(root,'fixture-plugin');d=path.dirname(d)) privatePath(d,true);
    if (digest(pin(p))!==inventory[f]) throw Error('fixture source pin mismatch');
  }
  function bind() {
  // Operator-owned RUNTIME state: not discovered native agent/plugin definitions.
  // Incomplete or forged bindings never permit an effect. No file writes here.
  const runtimePins=new Map();
  const read=relative=>{
    const p=path.join(root,relative);privatePath(p);const bytes=fs.readFileSync(p);
    runtimePins.set(p,digest(bytes));return JSON.parse(bytes);
  };
  const host=read('home/desk/native-host.json'),registry=read('home/desk/registry.json'),routes=read('home/desk/routes.json');
  const pointers={desk:read('home/desk.json'),chief:read('home/chief.json')};
  const managed=host.knowledge;
  if (!managed || !path.isAbsolute(managed.source||'') || !/^[a-f0-9]{64}$/.test(managed.sha256||'')
      || !/^[a-f0-9]{64}$/.test(managed.descriptor_sha256||'')) throw Error('managed source/descriptor pin pending');
  const managedCheck=()=>{
    const s=fs.lstatSync(managed.source);
    if (fs.realpathSync(managed.source)!==managed.source || !s.isFile() || s.nlink!==1 || (s.mode&0o022)
        || ![0,process.getuid()].includes(s.uid) || digest(fs.readFileSync(managed.source))!==managed.sha256) throw Error('managed source replaced/unsafe');
  };
  managedCheck();
  if (host.version!==1 || host.enabled!==true || host.desk_agent!=='proof-desk' || host.chief_agent!=='proof-chief'
      || host.overview_create!==true || !host.home_nativeProjectID || !host.home_projectId
      || Object.keys(host.projects||{}).sort().join()!=='lead-a,lead-b'
      || registry.version!==1 || Object.keys(registry.projects||{}).sort().join()!=='lead-a,lead-b'
       || routes.version!==1
      || Object.keys(routes.projects||{}).sort().join()!=='lead-a,lead-b') throw Error('fixture binding pending/invalid');
  const bindings=[];
  for (const [agent,{role,location:dir}] of Object.entries(agents)) {
    const directory=path.join(root,dir);
    let sessionID,projectID;
    if (role==='lead') {
      const b=host.projects[dir],r=registry.projects[dir],route=routes.projects[dir];
      if (!b || b.enabled!==true || b.lead_agent!==agent || !b.nativeProjectID || !b.projectId || b.note_create!==true
          || r?.path!==directory || r.log!==path.join(directory,'LEAD.md') || r.leads?.length!==1
          || route?.enabled!==true || route.epoch!==1 || JSON.stringify(route.leads)!==JSON.stringify(r.leads)) throw Error('fixture lead binding pending/invalid');
      sessionID=r.leads[0];projectID=b.nativeProjectID;
    } else {
      if (pointers[role]?.directory!==path.join(root,'home')) throw Error('fixture pointer mismatch');
      sessionID=pointers[role].session;projectID=host.home_nativeProjectID;
    }
    if (!/^ses_[A-Za-z0-9]+$/.test(sessionID) || typeof projectID!=='string') throw Error('actual native IDs required');
    bindings.push({agent,directory,sessionID,projectID});
  }
   if (new Set(bindings.map(b=>b.sessionID)).size!==4 || new Set([host.home_projectId,...Object.values(host.projects).map(b=>b.projectId)]).size!==3) throw Error('fixture identity/scope collision');
   const rules=Object.values(registry.rules||{});
   if(rules.length) {
     if(rules.length!==1 || Object.keys(registry.rules)[0]!=='fixture-first-smoke') throw Error('fixture ACK rule only');
     const manifest=read('evidence/binding-manifest.json');
     validateAck(rules[0],manifest.report,bindings.find(b=>b.agent==='proof-lead-a').sessionID);
     if(JSON.stringify(manifest.report)!==JSON.stringify(benignReport(manifest.report.observed))) throw Error('fixed benign report required');
   }
  return {host,bindings,check(){
    managedCheck();
    for (const [p,h] of runtimePins) {privatePath(p);if (digest(fs.readFileSync(p))!==h) throw Error('bound fixture runtime replaced');}
  }};
  }
  let sealed;
  const fixed={version:1,enabled:true,desk_agent:'proof-desk',chief_agent:'proof-chief',
    projects:{'lead-a':{lead_agent:'proof-lead-a'},'lead-b':{lead_agent:'proof-lead-b'}}};
  const check=()=>{
    sealed?.check();
    privatePath(root,true);parents(root);
    for (const d of ['home','lead-a','lead-b','fixture-plugin','.opencode','home/desk']) privatePath(path.join(root,d),true);
    discovery(root);
    for (const [p,h] of pins) {
      for (let d=path.dirname(p);d!==root;d=path.dirname(d)) privatePath(d,true);
      privatePath(p);if (digest(fs.readFileSync(p))!==h) throw Error('fixture pinned source/config replaced');
    }
  };
  const ready=()=>{check();if (!sealed) sealed=bind();sealed.check();return sealed;};
  // Captured object references stay host-private, bounded and never grant authority.
   // Only the post-native-verified private hook can execute fixed empty-canary probes.
  const captures=[];
  return {root,home:path.join(root,'home'),python,check,ready,isReady:()=>!!sealed, // file seal ONLY, never native identity/admission
    acceptsAgent:agent=>agents[agent]!==undefined && path.join(root,agents[agent].location)===location.directory,
    config:()=>sealed?.host || fixed,
     capture(name,c){if (captures.length>=16) throw Error('fixture context observation cap');captures.push({name,c});},
     release(){captures.length=0;},
     native(s) {
       const state=ready(),b=state.bindings.find(b=>b.sessionID===s.id);
       if(!b || s.agent!==b.agent || s.projectID!==b.projectID || s.location?.directory!==b.directory || s.time?.archived
         || state.host.current_model && state.host.current_model!==s.model?.providerID+'/'+s.model?.id) throw Error('fixture current native identity/model drift');
     },
     caller(c,s) {
    const b=ready().bindings.find(b=>b.sessionID===c.sessionID && b.agent===c.agent && b.directory===location.directory);
     if (!b || s.id!==b.sessionID || s.agent!==b.agent || s.projectID!==b.projectID || s.location?.directory!==b.directory || s.time?.archived) throw Error('fixture native caller refused');
     const model=ready().host.current_model;
     if(model && model!==s.model?.providerID+'/'+s.model?.id) throw Error('fixture current native model drift');
   }};
}

export default {id:'chief-desk-native-fixture',async setup(ctx) {
  // Crucially: no reading location/files or installing hooks on the default path.
  if (ctx.options?.enabled!==true) return;
   const policy=preflight(ctx.options,ctx.location);
  if (fileURLToPath(import.meta.url)!==path.join(policy.root,'fixture-plugin/hosts/desk-native/fixture-entry.mjs')) throw Error('entry must execute from pinned fixture package');
  let lease=leases.get(policy.root);
  if (!lease) {lease={stopped:false,entries:new Map(),controller:new AbortController()};leases.set(policy.root,lease);}
  if (lease.stopped || lease.entries.has(ctx.location.directory)) throw Error('fixture lifecycle already owned/stopped; no replacement');
   const snapshot=policy.check;
   // Compatibility with old pending fixtures: absent bootstrap leaves the metadata
   // collector pending, never guessed. New operator kit stages it before load.
   let proof;
   const bootstrap=path.join(policy.root,'bootstrap-source.json');
   if(fs.existsSync(bootstrap)) {
     privatePath(bootstrap);const bytes=fs.readFileSync(bootstrap),source=JSON.parse(bytes);
     privatePath(path.join(policy.root,'evidence'),true);
     const sourceCheck=()=>{snapshot();privatePath(bootstrap);if(digest(fs.readFileSync(bootstrap))!==digest(bytes)) throw Error('bootstrap pin drift');};
     const verifiedIDs=new Set();
     proof=observer({root:policy.root,directory:ctx.location.directory,source,check:sourceCheck,
       admit:()=>{if(lease.stopped || (lease.eventCount=(lease.eventCount||0)+1)>128) {lease.stopped=true;lease.controller.abort();throw Error('root evidence STOP/cap');}}});
     policy.metadata=proof.metadata;
     policy.catalog=proof.catalog;
     policy.start=()=>{
       if(!lease.watchdog) {lease.started=Date.now();lease.watchdog=setTimeout(()=>{void stop();},120000);lease.watchdog.unref?.();}
     };
     policy.verified=async(c,actual,seams)=>{
       try {const guarded=await proof.guard(c,actual,seams);verifiedIDs.add(actual.id);return guarded;}
       catch(error) {void stop();throw error;}
     };
     policy.observed=(kind,op,input,value)=>proof.record(kind,{op,input,value});
     policy.watches=event=>verifiedIDs.has(event.data?.sessionID) && ['session.execution.succeeded','session.execution.failed','session.execution.interrupted'].includes(event.type);
     policy.finish=async()=>{
       const paths=['evidence/binding-manifest.json','evidence/home.json','evidence/lead-a.json'].map(p=>path.join(policy.root,p));
       if(paths.some(p=>!fs.existsSync(p))) return; // wait only for bounded actual events, never poll/replay
       const values=paths.map(p=>{privatePath(p);return JSON.parse(fs.readFileSync(p));});
       const result=validateSmoke(values[0],values.slice(1));
       if(result.state==='correlated-first-smoke-only') {
         const p=path.join(policy.root,'evidence/correlation.json');
         fs.writeFileSync(p,JSON.stringify(result),{mode:0o600,flag:'wx'});await stop();
       }
     };
   }
   else policy.verified=()=>{throw Error('operator metadata bootstrap pending');};
  policy.signal=lease.controller.signal;
  policy.check=()=>{if (lease.stopped) throw Error('fixture lifecycle stopped');snapshot();};
  const entryState={cleanup:undefined,initializing:true};
  lease.entries.set(ctx.location.directory,entryState);
  const stop=async()=>{
     lease.stopped=true;
     clearTimeout(lease.watchdog);proof?.stop();policy.release();
    lease.controller.abort();
    let unresolved=0,quiesced=true;
     for (const state of lease.entries.values()) {
      const result=await state.cleanup?.();
      unresolved+=(result?.unresolved||0);
      quiesced=quiesced && !state.initializing && result?.quiesced===true;
     }
      if(proof && !lease.cleanupRecorded) {
       lease.cleanupRecorded=true;
       privatePath(path.join(policy.root,'evidence'),true);
       fs.writeFileSync(path.join(policy.root,'evidence/cleanup.json'),JSON.stringify({stopped:true,unresolved,quiesced,
         limits:'observation fencing only; inspect exact owned session status and IDs, never infer native cancellation'}),{mode:0o600,flag:'wx'});
      }
      if(proof && [...lease.entries.values()].every(s=>s.ended) && !lease.finalRecorded) {
        lease.finalRecorded=true;privatePath(path.join(policy.root,'evidence'),true);
        fs.writeFileSync(path.join(policy.root,'evidence/cleanup-final.json'),JSON.stringify({stopped:true,unresolved,quiesced,
          limits:'all owned subscriptions ended; underlying unary operations still require exact native readbacks'}),{mode:0o600,flag:'wx'});
      }
     return {unresolved,quiesced}; // ROOT-wide, not just this location
   };
   policy.ended=()=>{
     entryState.ended=true;
     if(lease.stopped && [...lease.entries.values()].every(s=>s.ended) && !lease.finalizing) {
       lease.finalizing=true;void stop().catch(()=>{}); // bounded diagnostics, not native retry/reconciliation
     }
   };
  try {
    // Registration is fixed from first load. No session/bridge/Knowledge read or
    // write before binding. Native identity is checked on each real tool operation.
    policy.check();
     const cleanup=await makePlugin({enabled:true,home:policy.home,python:policy.python},{fixture:policy}).setup(ctx);
     entryState.cleanup=()=>{policy.release();proof?.stop();return cleanup();};
    entryState.initializing=false;
    policy.check();
  } catch (error) {entryState.initializing=false;await stop();throw error;}
  return stop;
}};
