// Operator-only host capability. Never discovers, authenticates anew, or starts a server.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';

const fail = () => { throw Error('goal binding unavailable/untrusted; operator setup required'); };
const inside = (root,p) => p===root || p.startsWith(root+path.sep);
export const isConcreteModel = model => typeof model==='string' && /^[^/\s]+\/[^\s]+$/.test(model) && model!=='openchamber/auto';
export function privatePath(file, directory=false) {
  if (typeof file!=='string' || !path.isAbsolute(file) || path.resolve(file)!==file) fail();
  let p=path.parse(file).root;
  for (const part of file.slice(p.length).split(path.sep)) {
    p=path.join(p,part);
    const s=fs.lstatSync(p);
    if (s.isSymbolicLink() || (s.uid!==process.getuid() && s.uid!==0) || (s.mode & 0o022)) fail();
    if (p!==file && !s.isDirectory()) fail();
    if (p===file && (directory ? !s.isDirectory() : !s.isFile())) fail();
  }
  const s=fs.statSync(file);
  if (s.uid!==process.getuid() || (s.mode & 0o077) || !(s.mode & 0o400) || (!directory && s.nlink!==1)) fail();
  return file;
}
export function validateOrigin(origin) {
  const u=new URL(origin);
  if (u.protocol!=='http:' || u.hostname!=='127.0.0.1' || !u.port || u.username || u.password || u.pathname!=='/' || u.search || u.hash || u.origin!==origin) fail();
  return origin;
}
export function validateAuth(auth) {
  if (!auth || Object.keys(auth).length!==1) fail();
  if (typeof auth.Authorization==='string' && /^Bearer [A-Za-z0-9._~+\/-]+=*$/.test(auth.Authorization)) return auth;
  if (typeof auth.Cookie==='string' && /^oc_ui_session(?:_\d+)?=[A-Za-z0-9._~-]+$/.test(auth.Cookie)) return auth;
  fail();
}
export async function requestJson(origin,auth,route,body,fetchImpl=fetch) {
  const response=await fetchImpl(origin+route,{method:body ? 'POST':'GET',redirect:'error',
    headers:{Accept:'application/json',...auth,...(body ? {'Content-Type':'application/json'}:{})},
    ...(body ? {body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(20000)});
  const value=await response.json();
  if (!response.ok) {
    const error=Error('OpenChamber request failed');
    if (/^ses_[A-Za-z0-9]+$/.test(value?.sessionId||'')) error.sessionId=value.sessionId;
    throw error;
  }
  return value;
}
export function serverIdentity(info) {
  const keys=['pid','startedAt','runtime','openchamberVersion','port'];
  if (!Number.isSafeInteger(info?.pid) || info.pid<=0 || typeof info.startedAt!=='string' || !Number.isFinite(Date.parse(info.startedAt)) ||
      !['desktop','web'].includes(info.runtime) || typeof info.openchamberVersion!=='string' || !Number.isInteger(info.port)) fail();
  return Object.fromEntries(keys.map(k=>[k,info[k]]));
}
export function loadBinding(config) {
  try {
    const file=config.goal_binding;
    if (!file || inside(config.home,file)) fail();
    privatePath(path.dirname(file),true);privatePath(file);
    const b=JSON.parse(fs.readFileSync(file,'utf8'));
    if (Object.keys(b).sort().join(',')!=='auth,home,lead_agent,origin,server,version' || b.version!==1 || b.home!==config.home || b.lead_agent!==config.lead_agent) fail();
    validateOrigin(b.origin);validateAuth(b.auth);serverIdentity(b.server);
    if (Number(new URL(b.origin).port)!==b.server.port) fail();
    return b;
  } catch { fail(); }
}
const decodeSession = value => value?.data ?? value;
export function boundGoalRequest(ctx,config,{fetchImpl=fetch}={}) {
  if (!config.goal_binding) return undefined;
  return async (payload,authority)=>{
    let posted=false,lockPath,attempt;
    try {
      if (!isConcreteModel(payload?.model)) throw Error('concrete explicit model required');
      const b=loadBinding(config),call=(route,body)=>requestJson(b.origin,b.auth,route,body,fetchImpl);
      const info=serverIdentity(await call('/api/system/info'));
      if (JSON.stringify(info)!==JSON.stringify(serverIdentity(b.server))) fail();
      // Match the actual caller on BOTH native contexts, not merely the web port.
      const caller=await ctx.session.get({sessionID:authority.sessionID});
      const remote=decodeSession(await call('/api/session/'+authority.sessionID));
      if (remote?.id!==authority.sessionID || remote.agent!==caller.agent || remote.time?.archived ||
          !Number.isFinite(caller.time?.created) || remote.time?.created!==caller.time.created ||
          fs.realpathSync(remote.location.directory)!==fs.realpathSync(caller.location.directory)) fail();
      if (authority.replacement) {
        const current=await call('/api/openchamber/sessions/'+authority.sessionID+'/metadata?directory='+encodeURIComponent(payload.directory));
        if (current?.metadata?.openchamber?.goal?.status!=='active') fail();
      }
      const stem=path.join(path.dirname(config.goal_binding),createHash('sha256').update(config.home+'\0'+payload.directory).digest('hex'));
      const lock=stem+'.lock',record=stem+'.json';
      // Lock is retained on EVERY uncertain result, across process/session restarts.
      const fd=fs.openSync(lock,'wx',0o600);fs.fsyncSync(fd);fs.closeSync(fd);
      const parentFd=fs.openSync(path.dirname(lock),'r');fs.fsyncSync(parentFd);fs.closeSync(parentFd);
      try {
        const previous=fs.existsSync(record) ? (privatePath(record),JSON.parse(fs.readFileSync(record,'utf8'))) : null;
        if (authority.replacement ? previous?.sessionId!==authority.sessionID : previous!==null) throw Error('outcome already dispatched or replacement lacks authority');
      } catch { fs.unlinkSync(lock); throw Error('goal authority refused'); }
      attempt={state:'uncertain',caller:authority.sessionID,directory:payload.directory,attemptedAt:new Date().toISOString()};
      fs.writeFileSync(lock,JSON.stringify(attempt),{mode:0o600});
      lockPath=lock;
      // No retry, including network, parse, HTTP error or post-create verification failure.
      posted=true;
      const result=await call('/api/openchamber/control',{action:'session.create',input:payload});
      if (/^ses_[A-Za-z0-9]+$/.test(result?.sessionId||'')) fs.writeFileSync(lock,JSON.stringify({...attempt,sessionId:result.sessionId}),{mode:0o600});
      const slash=payload.model.indexOf('/');
      if (result?.partial || result?.error || result?.promptError || result?.goalEnabled!==true || result?.promptDispatched!==true || result?.dispatchedAsCommand!==false ||
          !/^ses_[A-Za-z0-9]+$/.test(result?.sessionId||'') || result.sessionId===authority.sessionID || result.directory!==payload.directory || result.agent!==config.lead_agent ||
          result.model?.providerID!==payload.model.slice(0,slash) || result.model?.modelID!==payload.model.slice(slash+1)) throw Error('unconfirmed create');
      const lead=await ctx.session.get({sessionID:result.sessionId});
      if (lead.agent!==config.lead_agent || lead.time?.archived || fs.realpathSync(lead.location.directory)!==payload.directory ||
          lead.model?.providerID!==payload.model.slice(0,slash) || lead.model?.id!==payload.model.slice(slash+1)) throw Error('native lead mismatch');
      const metadata=await call('/api/openchamber/sessions/'+result.sessionId+'/metadata?directory='+encodeURIComponent(payload.directory));
      const goal=metadata?.metadata?.openchamber?.goal;
      if (typeof goal?.id!=='string' || !goal.id || goal.status!=='active') throw Error('saved goal not active');
      const temp=record+'.tmp';
      const recordFd=fs.openSync(temp,'wx',0o600);
      try { fs.writeFileSync(recordFd,JSON.stringify({sessionId:result.sessionId}));fs.fsyncSync(recordFd); }
      finally { fs.closeSync(recordFd); }
      fs.renameSync(temp,record);
      const dirFd=fs.openSync(path.dirname(record),'r');
      try { fs.fsyncSync(dirFd);fs.unlinkSync(lock);fs.fsyncSync(dirFd); }
      finally { fs.closeSync(dirFd); }
      return {sessionId:result.sessionId,directory:payload.directory,goalEnabled:true,promptDispatched:true};
    } catch (error) {
      if (posted && lockPath && /^ses_[A-Za-z0-9]+$/.test(error?.sessionId||'')) {
        try { fs.writeFileSync(lockPath,JSON.stringify({...attempt,sessionId:error.sessionId}),{mode:0o600}); } catch { /* Original lock still blocks replay. */ }
      }
      throw Error(posted ? 'goal dispatch uncertain; operator must reconcile outcome; DO NOT replay' : 'goal binding/identity/authority unavailable; no create sent (reconcile any existing outcome lock)');
    }
  };
}
