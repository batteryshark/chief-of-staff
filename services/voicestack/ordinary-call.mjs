// Ordinary deployed CLI only. No managed grants, backend rewrite or direct socket access.
import {spawn} from 'node:child_process';
import {readFile,lstat,realpath,open} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const sessionID=s=>typeof s==='string'&&/^ses_[A-Za-z0-9]{1,100}$/.test(s);
const stable=s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,200}$/.test(s);
const text=(s,max)=>typeof s==='string'&&s.trim()&&s.length<=max&&!/[\x00-\x1f\x7f\uD800-\uDFFF]/u.test(s);
const absolute=s=>typeof s==='string'&&path.isAbsolute(s)&&path.normalize(s)===s;
const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).length===keys.length&&keys.every(k=>Object.hasOwn(o,k));
const sha=b=>createHash('sha256').update(b).digest('hex');
export const inputSchema={type:'object',additionalProperties:false,required:['operation_id','reason','title','body'],properties:{
  operation_id:{type:'string',pattern:uuid.source},reason:{type:'string',enum:['decision','goal-risk']},
  title:{type:'string',minLength:1,maxLength:100},body:{type:'string',minLength:1,maxLength:1000}}};
export const operationBudgetMs=200000; // 150s speech + 15s send + 15s receipt loop + last <=15s status read.
const result=(id,state,reason)=>({version:1,operation_id:id,state,...(reason?{reason}:{})});

export function ordinaryArgv(root,input,caller) {
  return [path.join(root,'bridge/reachout.mjs'),'send','--kind','urgent-call','--reason',input.reason,
    '--session',caller.sessionID,'--id',input.operation_id,'--title',input.title,'--body',input.body,
    '--message-id',caller.messageID];
}

const deliveries=new Set(['call-intent','not-called','apns-accepted','apns-rejected','delivery-unknown','dispatch-limit','revoked','no-token']);
const reasons=new Set(['urgent-eligible','calls-disabled','no-voip-token','call-outstanding','call-expired','phone-quiet-hours']);
const receipts=new Set(['reported','ringing','answered','declined','ended','report-failed','expired']);
export function sanitizeResult(id,code,stdout) {
  const uncertain=()=>result(id,'unknown','inspect-status-no-replay');
  let value;try {value=JSON.parse(stdout);} catch {return uncertain();}
  if(value?.id!==id)return uncertain();
  if(code===1&&value.outcome==='refused'&&value.reason==='speech_not_ready')return result(id,'not-sent','speech-not-ready');
  if(code!==0||value.error||!Array.isArray(value.targets)||!value.targets.length||value.targets.length>32)return uncertain();
  // First send snapshot can precede APNs/phone receipt. Never promote intent to ring/media.
  const targets=value.targets.map(t=>({delivery:deliveries.has(t?.delivery)?t.delivery:'unknown',
    policy:reasons.has(t?.policyReason)?t.policyReason:'unknown',receipt:receipts.has(t?.receipt)?t.receipt:'unknown'}));
  let phoneReceipt='unknown',quietUntil;
  if(['ringing','answered','declined','ended'].includes(value.answer))phoneReceipt=value.answer;
  else if(value.answer==='the phone could not show the call (not retried)')phoneReceipt='report-failed';
  else if(value.answer==='no answer before the ring deadline (not retried)')phoneReceipt='expired';
  else if(/^ended \((requested|declined|ringExpired|admissionRejected|reportRejected|providerReset|answerTimeout|answerFailed|readinessTimeout|actionTimeout|mediaFailed|mediaReset|policyRestricted|targetChanged)\)$/.test(value.answer??''))phoneReceipt='ended';
  else if(value.answer==='declined by the phone: calls are off on the phone, or it could not take a call now')phoneReceipt='declined';
  else if(value.answer==='declined: in quiet hours all day'){phoneReceipt='declined';quietUntil='all-day';}
  else {
    const match=/^declined: in quiet hours until ((?:[01][0-9]|2[0-3]):[0-5][0-9])$/.exec(value.answer??'');
    if(match){phoneReceipt='declined';quietUntil=match[1];}
  }
  return {...result(id,'recorded'),targets,phoneReceipt,...(quietUntil?{quietUntilLocal:quietUntil}:{}),
    ...(value.coalesced===true?{coalesced:true}:{}),media:'not-proven'};
}

async function caller(ctx,c,config) {
  const pointer=JSON.parse(await readFile(config.chiefPointerFile,'utf8'));
  if(pointer.session!==c.sessionID||pointer.directory!==config.directory||c.agent!==config.agentID)throw Error('caller');
  const signal=AbortSignal.any([c.signal,AbortSignal.timeout(1000)]);
  const lookup=ctx.session.get({sessionID:c.sessionID},{signal});
  let abort;
  const cancelled=new Promise((_,reject)=>{abort=()=>reject(Error('caller'));signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();});
  let raw;try {raw=await Promise.race([lookup,cancelled]);} finally {signal.removeEventListener('abort',abort);}
  const s=raw?.data??raw;
  if(signal.aborted||s?.id!==c.sessionID||s.agent!==config.agentID||s.location?.directory!==config.directory||s.time?.archived)throw Error('caller');
  // Re-read after native lookup, preserving the existing current-chief authority.
  const fresh=JSON.parse(await readFile(config.chiefPointerFile,'utf8'));
  if(fresh.session!==pointer.session||fresh.directory!==pointer.directory)throw Error('caller');
}
async function fence(config,input,c) {
  const dir=await lstat(config.attemptDirectory);
  if(!dir.isDirectory()||dir.isSymbolicLink()||dir.uid!==process.getuid()||(dir.mode&0o077)||await realpath(config.attemptDirectory)!==config.attemptDirectory)throw Error('private attempt directory');
  // Exact id is permanently fenced BEFORE CLI admission; never store title/body.
  const fd=await open(path.join(config.attemptDirectory,input.operation_id+'.json'),'wx',0o600);
  try {await fd.writeFile(JSON.stringify({version:1,operation_id:input.operation_id,session:c.sessionID,
    message:c.messageID,call:c.id,inputDigest:sha(JSON.stringify(input)),state:'attempt-reserved-no-replay'})+'\n');await fd.sync();}
  finally {await fd.close();}
  const parent=await open(config.attemptDirectory,'r');try {await parent.sync();} finally {await parent.close();}
}

export function createOrdinaryCallPlugin(binding) {
  if(binding&&(!exact(binding,['nodePath','codeRoot','chiefPointerFile','directory','agentID','attemptDirectory','cliSha256'])||
    !['nodePath','codeRoot','chiefPointerFile','directory','attemptDirectory'].every(k=>absolute(binding[k]))||
    !stable(binding.agentID)||!/^[a-f0-9]{64}$/.test(binding.cliSha256)))throw Error('Invalid ordinary call binding');
  const config=binding&&Object.freeze({...binding});
  return {id:'chief-ordinary-call',async setup(ctx) {
    if(!config)return;
    const registration=await ctx.tool.transform(editor=>editor.add({name:'chief_urgent_call',options:{codemode:false,permission:'chief_urgent_call'},input:inputSchema,
      description:'Chief: ordinary urgent call; no retries. See reset-reporting.',
      async execute(input,c) {
        const id=typeof input?.operation_id==='string'&&uuid.test(input.operation_id)?input.operation_id:null;
        const out=x=>({content:JSON.stringify(x)});
        if(!exact(input,['operation_id','reason','title','body'])||!id||!['decision','goal-risk'].includes(input.reason)||
          !text(input.title,100)||!text(input.body,1000)||/\bmilestone\b/i.test(input.title+' '+input.body)||
          !sessionID(c?.sessionID)||!stable(c.agent)||!stable(c.messageID)||!stable(c.id)||!(c.signal instanceof AbortSignal)||c.signal.aborted)
          return out(result(id,'refused','invalid-request'));
        const body={...input};const invocation={sessionID:c.sessionID,agent:c.agent,messageID:c.messageID,id:c.id,signal:c.signal};
        // Native permission errors propagate. No permissions are installed here.
        await ctx.permission.assert({sessionID:c.sessionID,agent:c.agent,source:{type:'tool',messageID:c.messageID,id:c.id},
          action:'chief_urgent_call',resources:['ordinary-urgent-call']});
        try {
          await caller(ctx,invocation,config);
          if(await realpath(config.codeRoot)!==config.codeRoot||sha(await readFile(path.join(config.codeRoot,'bridge/reachout.mjs')))!==config.cliSha256)
            return out(result(id,'refused','reviewed-cli-changed'));
          if(c.signal.aborted)return out(result(id,'refused','cancelled-before-attempt'));
          await fence(config,body,invocation);
        } catch(error) {return out(result(id,'refused',error.code==='EEXIST'?'already-attempted-inspect-status':'binding-or-attempt-unavailable'));}
        return out(await invoke(config,body,invocation));
      }}));
    return async()=>{await registration?.dispose();};
  }};
}

function invoke(config,input,c) {
  return new Promise(resolve=>{
    const unknown=()=>result(input.operation_id,'unknown','inspect-status-no-replay');
    if(c.signal.aborted){resolve(unknown());return;}
    let child;try {child=spawn(config.nodePath,ordinaryArgv(config.codeRoot,input,c),
      {cwd:config.codeRoot,shell:false,env:{},stdio:['ignore','pipe','pipe']});} catch {resolve(unknown());return;}
    let stdout='',bytes=0,errors=0,invalid=false;
    const stop=()=>{invalid=true;child.kill('SIGKILL');};
    const timer=setTimeout(stop,operationBudgetMs);
    c.signal.addEventListener('abort',stop,{once:true});if(c.signal.aborted)stop();
    child.stdout.on('data',chunk=>{bytes+=chunk.length;if(bytes>65536)stop();else stdout+=chunk.toString('utf8');});
    // Real CLI prints its first-receipt line on stderr even on success. Discard it;
    // use only sanitized JSON stdout, never echo private errors/request text.
    child.stderr.on('data',chunk=>{errors+=chunk.length;if(errors>4096)stop();});
    child.on('error',()=>{invalid=true;});
    child.on('close',code=>{clearTimeout(timer);c.signal.removeEventListener('abort',stop);
      resolve(invalid?unknown():sanitizeResult(input.operation_id,code,stdout));});
  });
}

export default createOrdinaryCallPlugin();
