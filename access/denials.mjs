// NON-LIVE pure observation/redaction candidate. No hooks, file writes or effects.
import path from 'node:path';
import { createHash } from 'node:crypto';

const nativeActions = new Set(['read','edit','external_directory','shell','grep','glob','execute','subagent','skill','question','webfetch','websearch']);
const effects = new Set(['allow','deny','ask']);
const safe = (value, pattern) => typeof value === 'string' && pattern.test(value) ? value : null;
const identifier = value => safe(value,/^[A-Za-z][A-Za-z0-9_.:-]{0,100}$/);
const sourceID = (value, prefix) => safe(value,new RegExp(`^${prefix}[A-Za-z0-9_-]{1,160}$`));
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const inside = (root, target) => root === target || target.startsWith(root+'/');
const timestamp = value => typeof value==='string' && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : new Date().toISOString();

function wildcard(value, pattern) {
  const escape = p => p.replaceAll('\\','/').replace(/[.+^${}()|[\]\\]/g,'\\$&').replaceAll('*','.*').replaceAll('?','.');
  const p = pattern.replaceAll('\\','/');
  const regex = p.endsWith(' *') ? escape(p.slice(0,-2))+'( .*)?' : escape(p);
  return new RegExp('^'+regex+'$','s').test(value.replaceAll('\\','/'));
}

export function redactPath(value, context, {boundary=false}={}) {
  if (typeof value !== 'string' || value.length>4096 || value.includes('\0')) return {value:null,status:'unavailable-or-unsafe'};
  const binding = context.compilation?.binding;
  if (!binding) return {value:null,status:'unbound'};
  const expanded = value.startsWith('~/') ? binding.home+value.slice(1) : value;
  const resolved = path.posix.resolve(binding.location,boundary && expanded.endsWith('/*') ? expanded.slice(0,-2) : expanded);
  // Explicit aliases only; never log arbitrary home paths, raw shell args or env.
  const root = (context.pathRoots ?? []).filter(r=>inside(r.path,resolved)).sort((a,b)=>b.path.length-a.path.length)[0];
  if (!root || !identifier(root.id)) return {value:null,status:'outside-bound-log-roots'};
  const parts = path.posix.relative(root.path,resolved).split('/').filter(Boolean);
  const protectedRoot = root.protected === true;
  // Syntax/entropy checks cannot detect arbitrary credential values in filenames.
  // Only explicitly reviewed public paths may retain tails; everything else is coarse.
  if (parts.length && (protectedRoot || !(context.publicPaths??[]).includes(resolved)))
    return {value:'@'+root.id+'/<redacted>',status:'redacted',kind:boundary?'directory-boundary':'path'};
  let redacted = protectedRoot && parts.length>0;
  const clean = protectedRoot ? (parts.length ? ['<redacted>'] : []) : parts.map(part => {
    if (!/^[A-Za-z0-9_. -]{1,80}$/.test(part) || /secret|token|password|credential|keychain|\.env|^eyJ/i.test(part)
        || /^[A-Za-z0-9_-]{32,}$/.test(part)) { redacted=true; return '<redacted>'; }
    return part;
  });
  return {value:'@'+root.id+(clean.length?'/'+clean.join('/'):''),status:redacted?'redacted':'bound-logical-path',kind:boundary?'directory-boundary':'path'};
}

function causes(error) {
  const result=[];
  for (let i=0;error && typeof error==='object' && i<6;i++) { result.push(error); error=error.error; }
  return result;
}

export function observeDenial(event, context) {
  if (event.status!=='error') return null;
  const chain=causes(event.error);
  const blocked=chain.find(e=>[e._tag,e.name,e.type].includes('Permission.BlockedError'));
  const generic=chain.some(e=>e.type==='permission.rejected');
  if (!blocked && !generic) return null; // Never parse arbitrary exception messages.
  const bound=Boolean(context.compilation && context.sessionID && context.agentID
    && context.sessionID===event.sessionID && context.agentID===event.agent);
  const compilation=bound?context.compilation:null;
  const knownActions=new Set([...nativeActions,...(compilation?.ruleManifest??[]).map(r=>r.action).filter(a=>a!=='*')]);
  const action=blocked && knownActions.has(blocked.permission)?blocked.permission:null;
  let denyingRule=null,deniedResource=null,ruleEvidence=blocked?'native-fields-unavailable':'serialized-error-rule-not-exposed';
  const exposedRules=blocked?.rules,resources=blocked?.resources;
  if (action && Array.isArray(exposedRules) && exposedRules.length<=512 && Array.isArray(resources) && resources.length<=16
      && resources.every(r=>typeof r==='string' && r.length<=4096)
      && exposedRules.every(r=>r && typeof r.action==='string' && r.action.length<=256
        && typeof r.resource==='string' && r.resource.length<=4096 && effects.has(r.effect))) {
    const denied=resources.map(resource=>({resource,rule:[...exposedRules].reverse().find(r=>wildcard(action,r.action)&&wildcard(resource,r.resource))})).find(r=>r.rule?.effect==='deny');
    const winner=denied?.rule;
    if (winner) {
      deniedResource=denied.resource;
      const candidates=(compilation?.ruleManifest??[]).filter(r=>r.action===winner.action&&r.resource===winner.resource&&r.effect===winner.effect);
      const mapped=candidates.length===1?candidates[0]:null;
      // No raw rule resource: shell patterns/unknown private paths may contain tokens.
      denyingRule=mapped && identifier(mapped.id)?{id:mapped.id,reason:identifier(mapped.reason),source:'native-rules-last-match'}:null;
      ruleEvidence=denyingRule?'native-deny-mapped-to-generated-rule':candidates.length>1
        ?'native-deny-present-generated-id-ambiguous':'native-deny-present-but-unmapped-redacted';
    } else ruleEvidence='native-rules-exposed-without-a-denying-rule';
  }
  let requested=null;
  if (bound) {
    if (['read','edit','external_directory'].includes(action)) requested=deniedResource??(Array.isArray(resources)?resources.find(r=>typeof r==='string'):null)??null;
    else if (!action && ['read','edit','write'].includes(event.tool)) requested=event.input?.path??null;
    else if (action==='shell') requested=event.input?.workdir??compilation.binding.location;
  }
  const pathRecord=redactPath(requested,bound?context:{},{boundary:action==='external_directory'});
  const knownTools=new Set([...knownActions,'write','patch']);
  const record={type:'permission-denial',observedAt:timestamp(context.observedAt),
    modelRevision:bound?identifier(compilation?.modelRevision):null,binding:bound?identifier(compilation?.binding.id):null,
    role:bound?identifier(compilation?.binding.role):'unbound',
    action,tool:knownTools.has(event.tool)?identifier(event.tool):'unmapped-tool',path:pathRecord,denyingRule,ruleEvidence,
    source:{session:sourceID(event.sessionID,'ses_'),message:sourceID(event.messageID,'msg_'),call:sourceID(event.id,'call_')},
    effects:'observation-only-no-retry-no-grant'};
  record.id=hash([record.source,record.action,record.tool,record.modelRevision]);
  return record;
}

// Only native asked/replied correlation proves plain rejection. An aborted tool alone
// is never evidence. Retain only sanitized request fields while waiting for a reply.
export function permissionObservation(request, context={}, call=null) {
  const bound=Boolean(call && context.compilation && context.sessionID===request.sessionID
    && context.sessionID===call.sessionID && context.agentID===call.agent);
  const compilation=bound?context.compilation:null;
  const known=new Set([...nativeActions,...(compilation?.ruleManifest??[]).map(r=>r.action).filter(a=>a!=='*')]);
  const action=known.has(request.action)?request.action:null;
  const resources=Array.isArray(request.resources)?request.resources:[];
  const resource=['read','edit','external_directory'].includes(action)&&resources.length===1?resources[0]:null;
  const tool=call && known.has(call.tool)?call.tool:null;
  return {modelRevision:bound?identifier(compilation.modelRevision):null,binding:bound?identifier(compilation.binding.id):null,
    role:bound?identifier(compilation.binding.role):'unbound',action,tool,
    path:redactPath(resource,bound?context:{},{boundary:action==='external_directory'}),
    source:{session:sourceID(request.sessionID,'ses_'),message:request.source?.type==='tool'?sourceID(request.source.messageID,'msg_'):null,
      call:request.source?.type==='tool'?sourceID(request.source.id,'call_'):null,request:sourceID(request.id,'per_')},
    resourceCount:resources.length,roleEvidence:bound?'explicit-binding-and-native-call':'unknown'};
}

export function observePermissionRejection(reply, asked=null, observedAt) {
  if (reply.type!=='permission.replied' || reply.data?.reply!=='reject') return null;
  const data=reply.data,session=sourceID(data.sessionID,'ses_'),request=sourceID(data.requestID,'per_');
  if (!session || !request) return null;
  const matched=asked?.source.session===session && asked?.source.request===request;
  const fields=matched?asked:{modelRevision:null,binding:null,role:'unbound',action:null,tool:null,
    path:{value:null,status:'unavailable-or-unsafe'},source:{session,message:null,call:null,request},roleEvidence:'unknown'};
  const record={type:'permission-denial',observedAt:timestamp(observedAt),...fields,denyingRule:null,
    ruleEvidence:matched?'native-asked-and-replied-reject':'native-reject-without-observed-request',
    source:{...fields.source,event:sourceID(reply.id,'evt_')},effects:'observation-only-no-retry-no-grant'};
  record.id=hash([session,request,'native-reject']);return record;
}

export function reviewRecord(observation, review, model) {
  const allowed=new Set(['disposition','reason','matrixCase','observedAt']);
  if (Object.keys(review).some(k=>!allowed.has(k))) throw Error('Review cannot grant, retry or alter permissions');
  if (!['correct-denial','model-defect','binding-gap','native-metadata-unknown'].includes(review.disposition)) throw Error('Explicit disposition required');
  if (review.reason!==undefined && !Object.hasOwn(model.reasons,review.reason)) throw Error('Unknown policy rationale');
  if (review.matrixCase!==undefined && !model.matrix.some(c=>c.id===review.matrixCase)) throw Error('Unknown regression case');
  if (review.disposition==='correct-denial' && !Object.hasOwn(model.reasons,review.reason)) throw Error('Correct denial needs a central policy rationale');
  if (review.disposition==='model-defect' && !model.matrix.some(c=>c.id===review.matrixCase)) throw Error('Model fix needs its matrix case');
  return {type:'denial-review-data',denial:observation.id,disposition:review.disposition,
    modelRevision:model.revision,observedModelRevision:observation.modelRevision,
    reason:identifier(review.reason),matrixCase:identifier(review.matrixCase),
    observedAt:timestamp(review.observedAt),effects:'none'};
}
