// Trusted OPERATOR/offline CLI only. No native, HTTP, SDK, auth or model imports.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {agents,pendingConfig} from './fixture-config.mjs';
import {fixtureAssets} from './fixture-assets.mjs';
import {validateSmoke} from './fixture-evidence.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
export const canonical=v=>JSON.stringify(v && typeof v==='object' ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
export function strictJSON(text) {
  if(Buffer.byteLength(text)>262144) throw Error('JSON bound');
  const tokens=text.match(/"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]|\S/g)||[];let i=0;
  function value() {
    const t=tokens[i++];
    if(t==='{') {const out={},seen=new Set();if(tokens[i]==='}') {i++;return out;}
      for(;;) {const k=JSON.parse(tokens[i++]);if(typeof k!=='string'||seen.has(k)||['__proto__','constructor','prototype'].includes(k)) throw Error('duplicate/unsafe JSON key');seen.add(k);
        if(tokens[i++]!==':') throw Error('JSON colon');out[k]=value();const end=tokens[i++];if(end==='}') return out;if(end!==',') throw Error('JSON comma');}}
    if(t==='[') {const out=[];if(tokens[i]===']') {i++;return out;}for(;;) {out.push(value());const end=tokens[i++];if(end===']') return out;if(end!==',') throw Error('JSON array');}}
    return JSON.parse(t);
  }
  // Native parser also rejects invalid escapes, whitespace and malformed numbers.
  JSON.parse(text);const out=value();if(i!==tokens.length) throw Error('JSON trailing data');return out;
}
export function privateFile(p) {
  const s=fs.lstatSync(p);
  if(fs.realpathSync(p)!==p || !s.isFile() || s.nlink!==1 || s.uid!==process.getuid() || s.mode&0o077) throw Error('private regular single-link file required');
  return s;
}
export function privateRoot(root) {
  if(!path.isAbsolute(root)||fs.realpathSync(root)!==root) throw Error('canonical root required');
  for(let d=root;;d=path.dirname(d)) {const s=fs.lstatSync(d);if(s.isSymbolicLink() || fs.existsSync(path.join(d,'.git'))) throw Error('linked/git ancestor refused');if(d===root && (!s.isDirectory()||s.uid!==process.getuid()||s.mode&0o077)) throw Error('private root required');if(path.dirname(d)===d) break;}
}
const read=p=>{privateFile(p);return strictJSON(fs.readFileSync(p,'utf8'));};
const write=(p,v)=>fs.writeFileSync(p,typeof v==='string'?v:JSON.stringify(v),{mode:0o600,flag:'wx'});
export const benignReport=observed=>({project:'lead-a',id:'first-smoke',source_revision:1,observed,
  landed:'Owned fixture report filed.',next:'Stop after first smoke.',your_part:null,state:'active',request:'ack',rule:'fixture-first-smoke'});
export function validateAck(rule,report,recipient,clock=Date.now()) {
  if(!rule || Object.keys(rule).sort().join()!==['id','project','action','active','fixture_only','report_hash','recipient','epoch','answer','evidence','expires'].sort().join()
      || canonical(report)!==canonical(benignReport(report?.observed)) || !Number.isFinite(Date.parse(report.observed))
      || rule?.id!=='fixture-first-smoke' || rule.project!=='lead-a' || rule.action!=='ack' || rule.active!==true
      || rule.report_hash!==hash(canonical(report)) || rule.recipient!==recipient || rule.epoch!==1
      || rule.answer!=='Filed. No approval implied.' || rule.evidence!=='trusted-operator-exact-benign-fixture'
      || rule.fixture_only!==true || !Number.isFinite(Date.parse(rule.expires)) || Date.parse(rule.expires)<=clock
      || Date.parse(rule.expires)>clock+120000 || Date.parse(report.observed)>clock+60000) throw Error('fixture exact ACK rule refused');
  return rule;
}
export function stage(root,python,source) {
  privateRoot(root);if(fs.readdirSync(root).length) throw Error('new EMPTY offline root required');
  if(fs.realpathSync(python)!==python || !fs.statSync(python).isFile() || fs.statSync(python).mode&0o022) throw Error('safe Python required');
  if(!source.endsWith('/agent-tool/openchamber-agent-tool/index.js')) throw Error('exact already-generated managed source path required');
  const ss=fs.lstatSync(source);if(fs.realpathSync(source)!==source || !ss.isFile()||ss.nlink!==1||![0,process.getuid()].includes(ss.uid)||ss.mode&0o022) throw Error('safe generated source required');
  const repo=fileURLToPath(new URL('../../',import.meta.url)),inventory={},copies=[];
  for(const f of fixtureAssets) {
    const p=path.join(repo,f==='scripts/progress.template.html'?'kits/chief/desk/progress.template.html':f),s=fs.lstatSync(p);
    if(fs.realpathSync(p)!==p || !s.isFile()||s.nlink!==1||s.mode&0o022) throw Error('unsafe source bundle');
    const b=fs.readFileSync(p);inventory[f]=hash(b);copies.push([f,b]);
  }
  // ALL input validation precedes ANY writes. Partial I/O failure leaves inert evidence;
  // never remove/retry a partially staged root as if no admission happened.
  for(const d of ['home/desk','lead-a','lead-b','fixture-plugin','.opencode','evidence']) fs.mkdirSync(path.join(root,d),{recursive:true,mode:0o700});
  for(const [f,b] of copies) {const p=path.join(root,'fixture-plugin',f);fs.mkdirSync(path.dirname(p),{recursive:true,mode:0o700});fs.writeFileSync(p,b,{mode:0o600,flag:'wx'});}
  write(path.join(root,'fixture-plugin/package.json'),strictJSON(fs.readFileSync(path.join(repo,'hosts/desk-native/fixture-package.json'),'utf8')));
  write(path.join(root,'fixture-plugin/fixture-source.json'),inventory);
  write(path.join(root,'.opencode/opencode.json'),pendingConfig(root,python)); // NEVER activates
  write(path.join(root,'bootstrap-source.json'),{source,sha256:hash(fs.readFileSync(source))});
  write(path.join(root,'owned-empty-canary'),'');
  write(path.join(root,'operator-manifest.json'),{version:1,root,python,inventory,ownership_nonce:randomUUID(),config_sha256:hash(fs.readFileSync(path.join(root,'.opencode/opencode.json'))),
    ownership:'operator-owned-fixture-not-native-identity',phase:'inert',expectedEpoch:1,plannedSessions:Object.keys(agents),
    sessions:[],uncertainty:'no native admissions attempted',limits:{runMs:120000,rpcMs:4000,turnMs:60000,events:128},effects:['fixture runtime','lead-a status Note','home overview Note','one synthetic receipt'],goals:false});
}
export function collect(root,input) {
  privateRoot(root);const manifest=read(path.join(root,'operator-manifest.json'));
  if(!input || Object.keys(input).sort().join()!==['quiescent','expectedEpoch','origin','model','observed','sessions','knowledge','rule'].sort().join()) throw Error('exact sanitized operator observation envelope required');
  if(manifest.root!==root || manifest.phase!=='inert' || input.quiescent!==true || input.expectedEpoch!==1 || input.origin!=='trusted-operator-saved-managed-responses') throw Error('operator quiescence/epoch required');
  if(!Array.isArray(input.sessions)||input.sessions.length!==4||!Array.isArray(input.knowledge)||input.knowledge.length!==3) throw Error('exact observation counts required');
  if(typeof input.model!=='string'||!/^[-\w.]+\/[-\w.]+$/.test(input.model)||/auto|claude/i.test(input.model)) throw Error('fixed non-Claude concrete model required');
  const expected=pendingConfig(root,manifest.python);expected.plugins[0].options.enabled=true;
  if(JSON.stringify(read(path.join(root,'.opencode/opencode.json')))!==JSON.stringify(expected)) throw Error('fixed definitions/config drift');
  const inventory=read(path.join(root,'fixture-plugin/fixture-source.json'));
  if(Object.keys(inventory).sort().join()!==fixtureAssets.slice().sort().join() || JSON.stringify(inventory)!==JSON.stringify(manifest.inventory)) throw Error('exact source inventory required');
  for(const f of fixtureAssets) {const p=path.join(root,'fixture-plugin',f);privateFile(p);if(hash(fs.readFileSync(p))!==inventory[f]) throw Error('source bundle pin drift');}
  const responseEvidence=o=>{
    if(typeof o.response_file!=='string' || path.dirname(o.response_file)!==path.join(root,'evidence')) throw Error('owned saved response required');
    privateFile(o.response_file);const bytes=fs.readFileSync(o.response_file);const saved=strictJSON(bytes.toString());
    if(hash(bytes)!==o.response_sha256) throw Error('saved tool response hash mismatch');
    const action=o.id?'session.list':'knowledge.list',directory=o.location?.directory||o.directory;
    if(saved.request?.action!==action || saved.request.parameters?.directory!==directory
      || saved.response?.schemaVersion!==1 || saved.response?.ok!==true || saved.response?.action!==action) throw Error('saved managed response/request scope mismatch');
    const data=saved.response.data;
    if(o.id) {
      const hits=data?.sessions?.filter(s=>s.id===o.id)||[],s=hits[0];
      if(saved.request.parameters.withStatus!==true || hits.length!==1 || s.agent!==o.agent || s.projectID!==o.projectID
        || s.location?.directory!==directory || s.model?.providerID+'/'+s.model?.id!==o.model || s.time?.archived
        || s.status?.type!=='idle' || !s.time || Object.keys(s.time).some(k=>!['created','updated','archived'].includes(k))
        || canonical(s.time)!==canonical(o.time)) throw Error('normalized/native managed-list observation/time mismatch');
    } else if(data?.projectId!==o.projectId) throw Error('normalized/managed namespace observation mismatch');
  };
  const ids=new Set(),byAgent=new Map();
  for(const s of input.sessions) {
    const def=agents[s.agent];
    if(Object.keys(s).sort().join()!==['id','agent','projectID','location','time','model','status','disabled','goalActive','response_file','response_sha256'].sort().join()
      || !def || byAgent.has(s.agent)||!/^ses_[A-Za-z0-9]+$/.test(s.id)||ids.has(s.id)||s.location?.directory!==path.join(root,def.location)
      || Object.keys(s.location).join()!=='directory' || !s.time || typeof s.time!=='object'
      || Object.keys(s.time).some(k=>!['created','updated','archived'].includes(k) || !Number.isFinite(s.time[k]))
      || typeof s.projectID!=='string'||!s.projectID||s.model!==input.model||s.status!=='idle'||s.disabled!==false||s.goalActive!==false||s.time?.archived
      || !/^[a-f0-9]{64}$/.test(s.response_sha256||'')) throw Error('ambiguous/malformed native observation');
    ids.add(s.id);byAgent.set(s.agent,s);
    responseEvidence(s);
  }
  const scopes=new Map();
  for(const k of input.knowledge) {
    if(Object.keys(k).sort().join()!==['directory','projectId','disabled','response_file','response_sha256'].sort().join()
      || !['home','lead-a','lead-b'].some(d=>path.join(root,d)===k.directory) || scopes.has(k.directory)
      || typeof k.projectId!=='string'||!k.projectId||k.disabled!==false||!/^[a-f0-9]{64}$/.test(k.response_sha256||'')) throw Error('managed scope observation required');
    scopes.set(k.directory,k.projectId);
    responseEvidence(k);
  }
  if(new Set(scopes.values()).size!==3) throw Error('managed namespace alias collision');
  const desk=byAgent.get('proof-desk'),chief=byAgent.get('proof-chief');
  if(desk.projectID!==chief.projectID) throw Error('home Core scope mismatch'); // global Core IDs across no-git scopes ARE allowed
  const snapshots=['home','lead-a','lead-b'].map(d=>read(path.join(root,'evidence','metadata-'+d+'.json')));
  const pin=read(path.join(root,'bootstrap-source.json'));
  for(const m of snapshots) if(m.source!==pin.source || m.sha256!==pin.sha256 || !/^[a-f0-9]{64}$/.test(m.descriptor_sha256||'') || m.descriptor_sha256!==snapshots[0].descriptor_sha256) throw Error('descriptor/source pending/drift');
  if(hash(fs.readFileSync(pin.source))!==pin.sha256) throw Error('managed source drift');
  const registry={version:1,projects:{},rules:{}},routes={version:1,projects:{}};
  const host={version:1,enabled:true,desk_agent:'proof-desk',chief_agent:'proof-chief',home_nativeProjectID:desk.projectID,home_projectId:scopes.get(path.join(root,'home')),overview_create:true,
    current_model:input.model,knowledge:{...pin,descriptor_sha256:snapshots[0].descriptor_sha256},projects:{}};
  for(const dir of ['lead-a','lead-b']) {
    const s=byAgent.get('proof-'+dir),directory=path.join(root,dir);
    host.projects[dir]={enabled:true,lead_agent:s.agent,nativeProjectID:s.projectID,projectId:scopes.get(directory),note_create:true};
    registry.projects[dir]={path:directory,log:path.join(directory,'LEAD.md'),leads:[s.id]};
    routes.projects[dir]={enabled:true,epoch:1,leads:[s.id]};
  }
  const report=benignReport(input.observed),rule=validateAck(input.rule,report,byAgent.get('proof-lead-a').id);
  registry.rules[rule.id]=rule;
  const outputs={'home/desk/native-host.json':host,'home/desk/registry.json':registry,'home/desk/routes.json':routes,
    'home/desk.json':{session:desk.id,directory:path.join(root,'home'),updated:input.observed},
    'home/chief.json':{session:chief.id,directory:path.join(root,'home'),updated:input.observed},
    'evidence/binding-manifest.json':{...manifest,config_sha256:hash(fs.readFileSync(path.join(root,'.opencode/opencode.json'))),metadataPins:snapshots,
      phase:'operator-bound-not-native-verified',sessions:input.sessions,knowledge:input.knowledge,report,rule,runClock:'START before first bound registered native get',responseEvidence:input}};
  // Runtime writer is absent-create only. Never overwrite partial/sealed bindings.
  const attempt='home/desk/operator-binding-attempt.json';
  const preflightOutputs=()=>{for(const rel of [...Object.keys(outputs),attempt]) {
    const p=path.join(root,rel);let exists=false;try {fs.lstatSync(p);exists=true;} catch(e) {if(e.code!=='ENOENT') throw e;}
    for(let d=path.dirname(p);d!==root;d=path.dirname(d)) {const s=fs.lstatSync(d);if(!s.isDirectory()||s.isSymbolicLink()||s.uid!==process.getuid()||s.mode&0o077) throw Error('runtime parent unsafe');}
    if(exists) throw Error('runtime destination already exists/linked');
  }};
  preflightOutputs();
  // Exclusive absent-create admission marker survives partial I/O failure. Entry
  // requires the complete binding manifest (written LAST); no partial seal/retry.
  write(path.join(root,attempt),{version:1,ownership:manifest.ownership,epoch:1,plannedPaths:Object.keys(outputs),
    uncertainty:'runtime write admitted; complete ONLY if final binding-manifest exists',at:new Date().toISOString()});
  for(const rel of Object.keys(outputs)) {if(fs.existsSync(path.join(root,rel))) throw Error('concurrent runtime writer; retain uncertain attempt');}
  for(const [rel,v] of Object.entries(outputs)) write(path.join(root,rel),v);
  return managedSteps(root,input.model,byAgent.get('proof-lead-a').id,report);
}
export function managedSteps(root,model,sessionId,report) {
  if(typeof model!=='string'||!/^[-\w.]+\/[-\w.]+$/.test(model)||/auto|claude/i.test(model)) throw Error('fixed non-Claude concrete model required');
  return {warning:'FUTURE AUTHORIZATION ONLY; JSON is not native proof. Never blind resend.',
    create:Object.entries(agents).map(([agent,{location}])=>({action:'session.create',parameters:{directory:path.join(root,location),agent,model,title:'OWNED native first-smoke '+agent}})),
    knowledge:['home','lead-a','lead-b'].map(d=>({action:'knowledge.list',parameters:{directory:path.join(root,d)}})),
    send:{action:'session.send',parameters:{directory:path.join(root,'lead-a'),sessionId,prompt:'Call desk_report exactly once with this exact JSON. Do not rewrite it, use other tools, or infer approval. '+JSON.stringify({report})}},
    desk:'No blind send: native prompt already queues exact input. If tool omitted, STOP unknown; inspect exact active input and retained action IDs.',
    stop:'Stop ingress, abort owned subscriptions via entry cleanup; inspect exact owned IDs. Never reload/replay. Retain unresolved admissions.'};
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const [command,root,a,b]=process.argv.slice(2);
  if(command==='stage-inert' && root && a && b) stage(root,a,b);
  else if(command==='bind' && root && a && !b) console.log(JSON.stringify(collect(root,read(a)),null,2));
  else if(command==='steps' && root && a && !b) {const steps=managedSteps(root,a,undefined,undefined);delete steps.send;console.log(JSON.stringify(steps,null,2));}
  else if(command==='rule' && root && a && b) {
    const report=benignReport(root),rule={id:'fixture-first-smoke',project:'lead-a',action:'ack',active:true,fixture_only:true,
      report_hash:hash(canonical(report)),recipient:a,epoch:1,answer:'Filed. No approval implied.',evidence:'trusted-operator-exact-benign-fixture',expires:b};
    console.log(JSON.stringify({report,rule:validateAck(rule,report,a)},null,2));
  }
  else if(command==='validate-evidence' && root && !a) {
    privateRoot(root);const result=validateSmoke(read(path.join(root,'evidence/binding-manifest.json')),
      ['home','lead-a'].map(d=>read(path.join(root,'evidence',d+'.json'))));
    const cleanup=read(path.join(root,'evidence/cleanup-final.json'));
    console.log(JSON.stringify({...result,cleanup,...(cleanup.stopped!==true || cleanup.unresolved!==0 || cleanup.quiesced!==true
      ? {state:'unknown-STOP',reason:'cleanup unresolved/unquiesced'}:{})},null,2));
  }
  else throw Error('usage: stage-inert F ABS_PYTHON GENERATED_SOURCE | steps F MODEL | rule OBSERVED ACTUAL_LEAD_ID EXPIRES | bind F PRIVATE_OBSERVATIONS_JSON | validate-evidence F');
}
