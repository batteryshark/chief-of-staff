// Host ONLY. Called from the actual registered executor after native get succeeds.
// Never exported as a tool. Offline callers/fake c prove source contracts only.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
const hash=x=>createHash('sha256').update(x).digest('hex');
export const descriptorHash=t=>hash(JSON.stringify({description:t.description,input:t.input,options:t.options}));
const identity=c=>({sessionID:c.sessionID,agent:c.agent,messageID:c.messageID,id:c.id});
export function observer({root,directory,check,source,admit=()=>{}}) {
  const events=[];let stopped=false,verified=0,started, timer;
  const guardedContexts=new WeakSet();
  const catalogs=new Map();
  const destination=path.join(root,'evidence',path.basename(directory)+'.json');
  const present=p=>{try {return fs.lstatSync(p);} catch(e) {if(e.code!=='ENOENT') throw e;}};
  if(present(destination)) throw Error('existing evidence; no replacement/replay');
  let written=false;
  const safe=p=>{const s=fs.lstatSync(p);if(fs.realpathSync(p)!==p||!s.isFile()||s.nlink!==1||![0,process.getuid()].includes(s.uid)||s.mode&0o022) throw Error('unsafe evidence/source path');};
  const privateEvidence=p=>{safe(p);const s=fs.lstatSync(p);if(s.uid!==process.getuid()||s.mode&0o077) throw Error('private evidence required');};
  const evidenceDirectory=()=>{const p=path.dirname(destination),s=fs.lstatSync(p);if(fs.realpathSync(p)!==p||!s.isDirectory()||s.uid!==process.getuid()||s.mode&0o077) throw Error('private evidence directory required');};
  function record(kind,data) {
    admit();
    evidenceDirectory();
    if(stopped || events.length>=128) {stopped=true;throw Error('fixture evidence STOP/cap');}
    if(written) privateEvidence(destination);
    if(JSON.stringify(data).length>65536) {stopped=true;throw Error('evidence item bound STOP');}
    events.push({seq:events.length+1,at:Date.now(),kind,data:JSON.parse(JSON.stringify(data))});
    if(JSON.stringify(events).length>1048576) {stopped=true;throw Error('evidence byte bound STOP');}
    fs.writeFileSync(destination,JSON.stringify({version:1,origin:'plugin-native-hook-not-operator-attestation',events}),{mode:0o600,flag:written?'w':'wx'});written=true;
  }
  function metadata(tools) {
    check();
    evidenceDirectory();
    if(tools.some(t=>t.id?.startsWith('openchamber_knowledge') && t.id!=='openchamber_knowledge')) throw Error('ambiguous managed alias namespace');
    const selected=tools.filter(t=>['read','write','openchamber_knowledge'].includes(t.id));
    if(new Set(selected.map(t=>t.id)).size!==selected.length) throw Error('ambiguous descriptor namespace');
    const t=selected.find(t=>t.id==='openchamber_knowledge');
    if(!t) return; // late descriptor remains pending; no invented registration event
    if(t.disabled===true || t.options?.codemode!==false) throw Error('managed descriptor disabled/unsupported');
    safe(source.source);
    if(source.sha256!==hash(fs.readFileSync(source.source))) throw Error('managed source drift');
    const cleanSchema=s=>JSON.parse(JSON.stringify(s,(key,value)=>['description','examples','default'].includes(key)?undefined:value));
    const snapshot={version:1,source:source.source,sha256:source.sha256,descriptor_sha256:descriptorHash(t),
      tools:selected.map(t=>({id:t.id,disabled:t.disabled===true,input:cleanSchema(t.input),options:{codemode:t.options?.codemode},descriptor_sha256:descriptorHash(t)}))};
    if(JSON.stringify(snapshot).length>32768) throw Error('metadata bound');
    // No descriptions, raw options/env/auth or executors are serialized.
    const file=path.join(root,'evidence','metadata-'+path.basename(directory)+'.json');
    const bytes=JSON.stringify(snapshot);
    if(present(file)) {privateEvidence(file);if(fs.readFileSync(file,'utf8')!==bytes) throw Error('descriptor changed');}
    else fs.writeFileSync(file,bytes,{mode:0o600,flag:'wx'});
  }
  async function guard(c,actual,{list,probe,observe}) {
    check();if(stopped) throw Error('fixture observer stopped');
    if(guardedContexts.has(c)) return true; // same private registered turn; caller/pins still checked again by adapter
    const catalog=catalogs.get(c.agent);
    const expected=c.agent.startsWith('proof-lead-')?['desk_report']:c.agent==='proof-desk'?['desk_inbox','desk_project_sync','desk_propose']:['desk_decision'];
    if(!catalog || catalog.names.join()!==expected.sort().join()) throw Error('actual request catalog pending/unsupported');
    if(++verified>16) throw Error('verified capture cap');
    if(!started) {started=Date.now();timer=setTimeout(()=>{stopped=true;},120000);timer.unref?.();}
    if(Date.now()-started>=120000) throw Error('fixture watchdog STOP');
    record('native-caller',{call:identity(c),native:{id:actual.id,agent:actual.agent,projectID:actual.projectID,location:actual.location}});
    record('catalog',{agent:c.agent,...catalog,limits:'current hook result; trusted operator must exclude later overriding plugins'});
    const tools=await observe(list);metadata(tools);
    const canary=path.join(root,'owned-empty-canary');
    const s=fs.lstatSync(canary);
    if(!s.isFile() || s.nlink!==1 || s.uid!==process.getuid() || s.mode&0o077 || s.size!==0) throw Error('owned EMPTY canary required');
    const specs=[['read',{path:canary,offset:1,limit:1},['path'],['path','offset','limit']],
      ['write',{path:canary,content:''},['path','content'],['path','content']],
      ['openchamber_knowledge',{action:'knowledge.list',parameters:{directory}},['action'],['action','parameters']]];
    for(const [id,args,required,allowed] of specs) {
      check();const hits=tools.filter(t=>t.id===id),t=hits[0];
      if(hits.length!==1 || t.disabled===true || typeof t.execute!=='function' || t.input?.type!=='object'
          || !required.every(k=>t.input.required?.includes(k))
          || t.input.required.some(k=>!allowed.includes(k))
          || !Object.keys(args).every(k=>k in (t.input.properties||{}))) throw Error('unsupported canary descriptor: '+id);
      const props=t.input.properties;
      if(id!=='openchamber_knowledge' && !supportedFileArgs(t.input,args)) throw Error('unsupported fixed file descriptor');
      if(id==='read' && (props.path.type!=='string' || !['integer','number'].includes(props.offset.type) || !['integer','number'].includes(props.limit.type))
        || id==='write' && (props.path.type!=='string'||props.content.type!=='string')
        || id==='openchamber_knowledge' && !supportedKnowledge(t.input)) throw Error('unsupported canary argument shape');
      const result=await probe(t,args,c); // private executor-boundary entry receipt, not error-text inference
      record('executor-denial',{id,call:identity(c),descriptor_sha256:descriptorHash(t),denied:result===true});
      if(result!==true || fs.statSync(canary).size!==0) {stopped=true;throw Error('canary unexpectedly allowed/unknown: STOP before projection');}
    }
    guardedContexts.add(c);return true;
  }
  return {metadata,guard,record,catalog(kind,event){catalogs.set(event.agent,{kind,names:Object.keys(event.tools).sort()});},stop(){stopped=true;catalogs.clear();clearTimeout(timer);return {events:events.length};}};
}
// Exactly the installed generator contract, not a general schema interpreter.
// Optional explicit parameters are supplied; every constraint on those fixed
// arguments must be understood. Unknown constraints/aliases STOP before probing.
function supportedKnowledge(s) {
  const keys=(o,allowed)=>o && typeof o==='object' && !Array.isArray(o) && Object.keys(o).every(k=>allowed.includes(k));
  const p=s.properties,a=p?.action,v=p?.parameters,d=v?.properties?.directory;
  return keys(s,['type','properties','required','additionalProperties']) && s.additionalProperties===true
    && Object.keys(p).sort().join()==='action,parameters' && s.required?.join()==='action'
    && keys(a,['type','oneOf','description']) && a.type==='string' && Array.isArray(a.oneOf) && a.oneOf.length>0
    && a.oneOf.every(b=>keys(b,['const','description']) && typeof b.const==='string')
    && new Set(a.oneOf.map(b=>b.const)).size===a.oneOf.length && a.oneOf.some(b=>b.const==='knowledge.list')
    && keys(v,['type','properties','additionalProperties','description']) && v.type==='object' && v.additionalProperties===false
    && keys(d,['type','description']) && d.type==='string';
}
function supportedFileArgs(s,args) {
  if(Object.keys(s).some(k=>!['type','properties','required','additionalProperties','description'].includes(k))) return false;
  for(const [key,value] of Object.entries(args)) {
    const p=s.properties[key];
    if(Object.keys(p).some(k=>!['type','description','default','minimum','maximum','minLength','maxLength'].includes(k))) return false;
    if(typeof value==='string') {
      if(p.type!=='string' || p.minimum!==undefined || p.maximum!==undefined
        || p.minLength!==undefined && (!Number.isSafeInteger(p.minLength)||value.length<p.minLength)
        || p.maxLength!==undefined && (!Number.isSafeInteger(p.maxLength)||value.length>p.maxLength)) return false;
    } else if(!['number','integer'].includes(p.type) || p.minLength!==undefined || p.maxLength!==undefined
      || p.minimum!==undefined && (!Number.isFinite(p.minimum)||value<p.minimum)
      || p.maximum!==undefined && (!Number.isFinite(p.maximum)||value>p.maximum)) return false;
  }
  return true;
}
