import path from 'node:path';

const object = x => x && typeof x === 'object' && !Array.isArray(x);
const exact = (x, keys) => object(x) && Object.keys(x).sort().join() === keys.sort().join();
const goalOK = g => exact(g, ['id','created_at']) && typeof g.id === 'string' && /^[A-Za-z0-9_-]{1,256}$/.test(g.id)
  && Number.isSafeInteger(g.created_at) && g.created_at > 0;
export function requestOK(q) {
  return exact(q, ['version','session','directory','goal']) && q.version === 1
    && typeof q.session === 'string' && /^ses_[A-Za-z0-9_-]{1,252}$/.test(q.session)
    && typeof q.directory === 'string' && q.directory.length <= 4096 && path.isAbsolute(q.directory)
    && !/[\x00-\x1f]/.test(q.directory) && path.normalize(q.directory) === q.directory && goalOK(q.goal);
}
export async function captureQuestionOrigin(caller, sessionID, metadata) {
  if (caller?.id !== sessionID || caller.time?.archived || !path.isAbsolute(caller.location?.directory ?? '')) throw Error('Native posting identity unavailable');
  const origin = {sessionID, directory:caller.location.directory};
  try {
    const g = (await metadata(sessionID, origin.directory))?.openchamber?.goal;
    const goal = {id:g?.id, created_at:g?.createdAt}; // Native milliseconds, not created_at.
    if (goalOK(goal) && goal.created_at <= Date.now()) origin.goal = goal;
  } catch { /* Unbound is deliberately observable as incomplete, never retrospectively adopted. */ }
  return origin;
}
export async function snapshot(bus, q, coverage, now = Date.now()) {
  if (!requestOK(q)) throw Error('Invalid request');
  const out = {version:1,source:'chief-question-status',observed_at:new Date(now).toISOString(),complete:false,
    session:q.session,directory:q.directory,goal:q.goal,questions:[],reason:'coverage unavailable'};
  const unknown = () => ({...out, questions:[], complete:false, reason:'source incomplete'});
  if (q.goal.created_at > now) return unknown();
  // Explicit operator assertion of this registered source's coverage, not all chat questions.
  if (!exact(coverage, ['version','scope','since','origins']) || coverage.version !== 1
      || coverage.scope !== 'registered-chief-post' || !Number.isSafeInteger(coverage.since)
      || coverage.since < 0 || coverage.since > now || !Array.isArray(coverage.origins)
      || !coverage.origins.every(o => exact(o,['session','directory']))
      || coverage.origins.filter(o=>o.session===q.session && o.directory===q.directory).length !== 1) return out;
  try {
    const inbox = JSON.parse(await bus.inbox());
    if (inbox.sourceComplete !== true || !Array.isArray(inbox.entries) || inbox.total !== inbox.entries.length || inbox.omitted !== 0 || inbox.total > 200) return unknown();
    const ids = new Set();
    for (const entry of inbox.entries) {
      if (!object(entry) || typeof entry.id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(entry.id)
          || ids.has(entry.id) || !object(entry.origin)) return unknown();
      ids.add(entry.id);
      if (entry.origin.sessionID !== q.session) continue;
      const {event:e, history} = await bus.detail(entry.id);
      if (!e || e.id !== entry.id || e.origin?.sessionID !== q.session || !Array.isArray(history)) return unknown();
      // Recorded answer or covered disposition is resolved regardless of reply delivery.
      if (e.closed || history.some(r=>['answer','close','chief-record-close'].includes(r.type)) || e.result?.route === 'covered' || e.result?.route === 'filed') continue;
      if (e.origin.directory !== q.directory || !goalOK(e.origin.goal) || !['urgent','normal'].includes(e.urgency)) return unknown();
      if (e.origin.goal.id !== q.goal.id || e.origin.goal.created_at !== q.goal.created_at) continue;
      if (!Number.isSafeInteger(e.at) || e.at < q.goal.created_at || e.at < coverage.since || e.at > now) return unknown();
      if (e.result && !['chief','principal'].includes(e.result.route)) return unknown();
      out.questions.push({id:'heartbeat:'+e.id,status:'unresolved',asked_at:new Date(e.at).toISOString(),
        session:q.session,directory:q.directory,goal:q.goal});
    }
    out.complete = true; delete out.reason;
    if (Buffer.byteLength(JSON.stringify(out)) > 32768) return unknown();
    return out;
  } catch { return unknown(); }
}
