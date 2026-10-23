import {spawn} from 'node:child_process';
import path from 'node:path';

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const stableID = s => typeof s === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(s);
const exact = (o, keys) => o && typeof o === 'object' && !Array.isArray(o) &&
  Object.keys(o).length === keys.length && keys.every(k => Object.hasOwn(o, k));
const text = (s, max) => typeof s === 'string' && s.length > 0 && s.length <= max && !/[\x00-\x1f\x7f]/.test(s);
const absolute = s => text(s, 1024) && path.isAbsolute(s) && !s.split('/').some(p => p === '.' || p === '..');
export const inputSchema = {
  type:'object', additionalProperties:false, required:['operation_id','reason','summary'],
  properties:{operation_id:{type:'string',pattern:uuid.source},
    reason:{type:'string',enum:['decision','goal-risk','voice-quicker']},
    summary:{type:'string',minLength:1,maxLength:240}},
};
function validBody(o) {
  return exact(o, ['operation_id','reason','summary']) && typeof o.operation_id === 'string' && uuid.test(o.operation_id) &&
    ['decision','goal-risk','voice-quicker'].includes(o.reason) && text(o.summary,240) && o.summary.trim() && !/\bmilestone\b/i.test(o.summary);
}
const refused = id => ({version:1,operation_id:id,state:'refused',reason:'request-refused'});
const unknown = id => ({version:1,operation_id:id,state:'unknown',reason:'transport-unconfirmed'});
const operationBudgetMs = 170000;

// Supported V2 SessionDomain.get returns Session.Info directly (no data wrapper).
// Call only with native ToolContext, never a model-selected invocation. No role
// is inferred here. Owner code may use this quartet to look up approved context.
export async function resolveNativeCaller(ctx, invocation, {signal = invocation?.signal} = {}) {
  try {
    const sessionID = invocation?.sessionID, agent = invocation?.agent;
    if (typeof sessionID !== 'string' || !/^ses_[A-Za-z0-9]{1,100}$/.test(sessionID) ||
        !stableID(agent) || !(signal instanceof AbortSignal) || signal.aborted) throw new Error();
    const boundedSignal = AbortSignal.any([signal, AbortSignal.timeout(1000)]);
    const session = await bounded(ctx.session.get({sessionID}, {signal:boundedSignal}), boundedSignal);
    if (boundedSignal.aborted || session?.id !== sessionID || session?.agent !== agent ||
        !stableID(session?.projectID) || !absolute(session?.location?.directory)) throw new Error();
    return Object.freeze({session_id:sessionID,agent_id:agent,
      project_id:session.projectID,directory:session.location.directory});
  } catch { throw new Error('Native caller metadata unavailable'); }
}

// Owner-code composition only. Supply the read-only callback pair returned by
// the owner's createManagedCallerResolvers({codeRoot}); never pass the module's
// provisioning/revocation exports. This wrapper performs no startup lookup.
export function createNativeManagedCallPlugin({nodePath, codeRoot, ownerResolvers, fixtureOnly=false}) {
  if (typeof ownerResolvers?.resolveCaller !== 'function' || typeof ownerResolvers?.resolveGrant !== 'function')
    throw new Error('Invalid managed call binding');
  const resolveCaller = ownerResolvers.resolveCaller.bind(ownerResolvers);
  const resolveGrant = ownerResolvers.resolveGrant.bind(ownerResolvers);
  // Validate fixed paths now using the existing factory, without running setup.
  createManagedCallPlugin({nodePath,codeRoot,resolveCaller,resolveGrant});
  return {
    id:'chief-call',
    async setup(ctx) {
      return createManagedCallPlugin({nodePath,codeRoot,resolveGrant,fixtureOnly,
        resolveCaller:async (invocation, options) =>
          resolveCaller(await resolveNativeCaller(ctx,invocation,options),options),
      }).setup(ctx);
    },
  };
}

// Owner-installed functions, never JSON plugin options or model inputs:
// resolveCaller({sessionID,agent,messageID,id}, {signal}) must read authenticated
// current runtime project/directory and an owner-authorized role. It must NOT use
// ctx.location, environment session IDs, chief pointers, or transcript claims.
// resolveNativeCaller(ctx, invocation, {signal}) supplies the native quartet;
// the owner's forthcoming approved-context resolver must supply/check the role.
// resolveGrant(context, {signal}) privately returns the exact immutable grant's
// token. No issuance/discovery/fallback is provided here. Production is UNBOUND.
export function createManagedCallPlugin(binding) {
  if (binding && (!absolute(binding.nodePath) || !absolute(binding.codeRoot) ||
      typeof binding.resolveCaller !== 'function' || typeof binding.resolveGrant !== 'function')) {
    throw new Error('Invalid managed call binding');
  }
  const config = binding && Object.freeze({...binding});
  return {
    id:'chief-call',
    async setup(ctx) {
      // Owner correction 22Oct: managed-call-v1 is deferred, NEVER deployed.
      // Only explicit offline fixture composition may register; valid paths and
      // resolver callbacks alone are not a deployed backend contract.
      if (!config || config.fixtureOnly!==true) return;
      await ctx.tool.transform(editor => editor.add({
        name:'chief_call', options:{codemode:false,permission:'chief_call'}, input:inputSchema,
        description:'Request managed voice contact. intent-admitted confirms durable intent only, never ringing, answer or media. Missing host returns blocked. Never automatically retry an uncertain result; timeout does not prove backend cancellation.',
        async execute(input, c) {
          const id = typeof input?.operation_id === 'string' && uuid.test(input.operation_id) ? input.operation_id : null;
          const result = value => ({content:JSON.stringify(value)});
          if (!validBody(input)) return result(refused(id));
          const body = {...input};
          if (c.signal.aborted || !/^ses_[A-Za-z0-9]{1,100}$/.test(c.sessionID) || !stableID(c.agent) || !text(c.messageID,256) || !text(c.id,256)) return result(refused(id));
          // Permission errors propagate with native denial semantics. No rules
          // are installed by this module; backend authentication remains required.
          await ctx.permission.assert({sessionID:c.sessionID,agent:c.agent,
            source:{type:'tool',messageID:c.messageID,id:c.id},
            action:'chief_call',resources:['managed-call-v1']});
          // Permission approval time is outside execution. This single monotonic
          // budget includes metadata/grant lookup, FD3, socket wait and return.
          const deadline = performance.now() + operationBudgetMs;
          try {
            const signal = AbortSignal.any([c.signal, AbortSignal.timeout(1000)]);
            const identity = Object.freeze({sessionID:c.sessionID,agent:c.agent,messageID:c.messageID,id:c.id});
            const context = await bounded(config.resolveCaller(identity,{signal}), signal);
            if (!exact(context,['version','role','session_id','agent_id','project_id','directory']) || context.version !== 1 ||
                !['chief','lead'].includes(context.role) || context.session_id !== c.sessionID || context.agent_id !== c.agent ||
                !stableID(context.project_id) || !absolute(context.directory)) return result(refused(id));
            const trusted = Object.freeze({...context});
            const token = await bounded(config.resolveGrant(trusted,{signal}), signal);
            if (typeof token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(token)) return result(refused(id));
            const envelope = {version:1,token,context:trusted};
            if (Buffer.byteLength(JSON.stringify({command:'managed-call-v1',value:{...envelope,body:{version:1,...body}}})+'\n') > 8192) return result(refused(id));
            return result(await invoke(body,envelope,config,c.signal,deadline));
          } catch { return result(refused(id)); }
        },
      }));
    },
  };
}

function bounded(promise, signal) {
  return new Promise((resolve,reject) => {
    let timer;
    const finish = (fn, value) => {clearTimeout(timer); signal.removeEventListener('abort',abort); fn(value);};
    const abort = () => finish(reject,new Error('Binding unavailable'));
    if (signal.aborted) { abort(); return; }
    timer = setTimeout(abort,1000);
    signal.addEventListener('abort',abort,{once:true});
    Promise.resolve(promise).then(v => finish(resolve,v), e => finish(reject,e));
  });
}

function invoke(body, envelope, config, signal, deadline) {
  return new Promise(resolve => {
    if (signal.aborted || performance.now() >= deadline) { resolve(refused(body.operation_id)); return; }
    let child;
    try {
      child = spawn(config.nodePath,[path.join(config.codeRoot,'bridge/reachout.mjs'),'managed-call-v1',
        '--operation-id',body.operation_id,'--reason',body.reason,'--summary',body.summary],
      {cwd:config.codeRoot,shell:false,env:{},stdio:['ignore','pipe','pipe','pipe']});
    } catch { resolve(refused(body.operation_id)); return; }
    let output = '', bytes = 0, invalid = false;
    const stop = () => { invalid = true; child.kill('SIGKILL'); };
    // Kill/await only our CLI. Backend work may still settle after disconnect.
    const timer = setTimeout(stop,Math.max(0,deadline - performance.now()));
    signal.addEventListener('abort',stop,{once:true});
    if (signal.aborted) stop();
    child.stdout.on('data',chunk => {
      bytes += chunk.length;
      if (bytes > 2048) stop();
      else output += chunk.toString('utf8');
    });
    // No child diagnostics, credentials, context or unvalidated output escapes.
    child.stderr.on('data',stop);
    child.on('error',() => { invalid = true; });
    child.stdio[3].on('error',stop);
    child.on('close',code => {
      clearTimeout(timer); signal.removeEventListener('abort',stop);
      let value;
      try { value = JSON.parse(output); } catch { /* sanitized below */ }
      if (!invalid && value?.version === 1 && value.operation_id === body.operation_id) {
        if (code === 0 && exact(value,['version','operation_id','state','call_id']) &&
            value.state === 'intent-admitted' && typeof value.call_id === 'string' && uuid.test(value.call_id)) {
          resolve({version:1,operation_id:body.operation_id,state:'intent-admitted',call_id:value.call_id}); return;
        }
        if (code === 1 && exact(value,['version','operation_id','state','reason']) &&
            (value.state === 'blocked' && value.reason === 'host-unavailable' ||
             value.state === 'refused' && value.reason === 'request-refused' ||
             value.state === 'unknown' && ['operation-uncertain','transport-unconfirmed'].includes(value.reason))) {
          resolve({version:1,operation_id:body.operation_id,state:value.state,reason:value.reason}); return;
        }
      }
      resolve(unknown(body.operation_id));
    });
    child.stdio[3].end(JSON.stringify(envelope));
  });
}

export default createManagedCallPlugin();
