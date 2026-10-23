// Native own-row capability. No roster path, owner, environment or command input.
import {spawn} from 'node:child_process';
import {readFile,realpath} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).length===keys.length&&keys.every(k=>Object.hasOwn(o,k));
const sid=s=>typeof s==='string'&&/^ses_[A-Za-z0-9]{1,100}$/.test(s);
const id=s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,200}$/.test(s);
const absolute=s=>typeof s==='string'&&path.isAbsolute(s)&&path.normalize(s)===s;
const hash=x=>createHash('sha256').update(x).digest('hex');
export const helperFiles=['docket/milestone.py','docket/checkins.py','docket/parse.py','docket/__init__.py'];
export const inputSchema={type:'object',additionalProperties:false,required:['milestone_at','milestone_ref'],properties:{
  milestone_at:{type:'string',minLength:1,maxLength:80},milestone_ref:{type:'string',minLength:1,maxLength:1000}}};
const refused=()=>({status:'refused',reason:'check-own-binding-time-privacy-or-conflict'});
const unknown=()=>({status:'unknown',reason:'inspect-existing-row-no-automatic-retry'});

export function createMilestonePlugin(binding) {
  if(binding&&(!exact(binding,['pythonPath','sourceRoot','home','callers','sourceHashes'])||
    !['pythonPath','sourceRoot','home'].every(k=>absolute(binding[k]))||!Array.isArray(binding.callers)||!binding.callers.length||
    binding.callers.some(c=>!exact(c,['sessionID','agentID','directory'])||!sid(c.sessionID)||!id(c.agentID)||!absolute(c.directory))||
    new Set(binding.callers.map(c=>c.sessionID)).size!==binding.callers.length||!exact(binding.sourceHashes,helperFiles)||
    helperFiles.some(p=>!/^[a-f0-9]{64}$/.test(binding.sourceHashes[p]))))throw Error('Invalid own milestone binding');
  const config=binding&&structuredClone(binding);
  return {id:'docket-own-milestone',async setup(ctx) {
    if(!config)return;
    const registration=await ctx.tool.transform(editor=>editor.add({name:'docket_milestone',options:{codemode:false,permission:'docket_milestone'},
      description:'Lead: record your own accepted milestone; no enrollment or retry.',input:inputSchema,
      async execute(input,c) {
        const output=value=>({content:JSON.stringify(value)});
        if(!exact(input,['milestone_at','milestone_ref'])||typeof input.milestone_at!=='string'||!input.milestone_at.trim()||input.milestone_at.length>80||
          typeof input.milestone_ref!=='string'||!input.milestone_ref.trim()||input.milestone_ref.length>1000||
          !sid(c?.sessionID)||!id(c.agent)||!id(c.messageID)||!id(c.id)||!(c.signal instanceof AbortSignal)||c.signal.aborted)return output(refused());
        const caller=config.callers.find(row=>row.sessionID===c.sessionID&&row.agentID===c.agent);
        if(!caller)return output(refused());
        const value={...input};
        await ctx.permission.assert({sessionID:c.sessionID,agent:c.agent,source:{type:'tool',messageID:c.messageID,id:c.id},
          action:'docket_milestone',resources:['own']});
        try {
          const signal=AbortSignal.any([c.signal,AbortSignal.timeout(1000)]);
          let abort;const cancelled=new Promise((_,reject)=>{abort=()=>reject(Error('identity'));signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();});
          let raw;try {raw=await Promise.race([ctx.session.get({sessionID:c.sessionID},{signal}),cancelled]);}
          finally {signal.removeEventListener('abort',abort);}
          const session=raw?.data??raw;
          if(signal.aborted||session?.id!==c.sessionID||session.agent!==caller.agentID||session.location?.directory!==caller.directory||session.time?.archived)return output(refused());
          if(await realpath(config.sourceRoot)!==config.sourceRoot)return output(refused());
          for(const file of helperFiles)if(hash(await readFile(path.join(config.sourceRoot,file)))!==config.sourceHashes[file])return output(refused());
          if(c.signal.aborted)return output(refused());
          return output(await invoke(config,caller,value,c.signal));
        } catch {return output(refused());}
      }}));
    return async()=>{await registration?.dispose();};
  }};
}

function invoke(config,caller,input,signal) {
  return new Promise(resolve=>{
    let child;
    try {child=spawn(config.pythonPath,['-E','-s','-B','-m','docket.milestone'],{cwd:config.sourceRoot,shell:false,
      env:{HOME:config.home,DOCKET_CALLER_SESSION:caller.sessionID,DOCKET_CALLER_DIRECTORY:caller.directory},stdio:['pipe','pipe','pipe']});}
    catch {resolve(unknown());return;}
    let stdout='',bytes=0,errors=0,uncertain=false;
    const stop=()=>{uncertain=true;child.kill('SIGKILL');};
    const timer=setTimeout(stop,10000);signal.addEventListener('abort',stop,{once:true});if(signal.aborted)stop();
    child.stdout.on('data',chunk=>{bytes+=chunk.length;if(bytes>8192)stop();else stdout+=chunk.toString('utf8');});
    child.stderr.on('data',chunk=>{errors+=chunk.length;if(errors>8192)stop();});
    child.stdin.on('error',()=>{uncertain=true;});child.on('error',()=>{uncertain=true;});
    child.on('close',code=>{
      clearTimeout(timer);signal.removeEventListener('abort',stop);
      if(uncertain){resolve(unknown());return;}
      let receipt;try {receipt=JSON.parse(stdout);} catch {resolve(unknown());return;}
      if(code===0&&exact(receipt,['status'])&&receipt.status==='unchanged'){resolve({status:'unchanged'});return;}
      if(code===0&&exact(receipt,['status','receipt_sha256'])&&receipt.status==='recorded'&&/^[a-f0-9]{64}$/.test(receipt.receipt_sha256)){
        resolve({status:'recorded',receipt_sha256:receipt.receipt_sha256});return;
      }
      // Helper can fail after replacement (e.g. directory fsync). Never classify
      // a nonzero result as proof that no write occurred, nor automatically retry.
      resolve(unknown());
    });
    child.stdin.end(JSON.stringify(input));
  });
}

export default createMilestonePlugin();
