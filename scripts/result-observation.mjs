// Owned fixture diagnostics only. Inspect values BEFORE JSON serialization.
export function jsonIssues(value, prefix='$', ancestors=new Set()) {
  if (value===null || ['string','boolean'].includes(typeof value)) return [];
  if (typeof value==='number') return Number.isFinite(value)?[]:[prefix+': nonfinite number'];
  if (typeof value!=='object') return [prefix+': '+typeof value];
  if (ancestors.has(value)) return [prefix+': cycle'];
  if (!Array.isArray(value) && ![Object.prototype,null].includes(Object.getPrototypeOf(value))) return [prefix+': non-JSON object'];
  const next=new Set(ancestors);next.add(value);
  return Object.keys(value).flatMap(key=>jsonIssues(value[key],prefix+'.'+key,next));
}

export function observeResult({stage,result,context,tool}) {
  const a2a=result?.metadata?.a2a;
  return {stage,tool,sessionID:context.sessionID,messageID:context.messageID,callID:context.id,agent:context.agent,
    ownParentID:!!a2a&&Object.hasOwn(a2a,'parentID'),parentIDType:typeof a2a?.parentID,
    contentLength:typeof result?.content==='string'?result.content.length:null,
    content:result?.content,destination:a2a?.to,nested:a2a?.nested,ok:a2a?.ok,
    metadataIssues:jsonIssues(result?.metadata),resultIssues:jsonIssues(result)};
}
