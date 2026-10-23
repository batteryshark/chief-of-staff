import path from 'node:path';
// Existing pointer/roster/hold readers remain the authority; no local allowlist.
import {recipientEligibility, projectHolds} from '../heartbeat/records.mjs';
import {chiefSelection} from '../heartbeat/chief.mjs';

const data = response => response?.data ?? response;
const require = (ok, message) => { if (!ok) throw Error(message); };
const sameOrigin = (a,b) => ['sessionID','messageID','callID','directory'].every(k=>a?.[k]===b?.[k]);

// Read the real OpenChamber archive overlay through its existing authenticated tool
// connection. Native Session.Info alone does not contain this app-owned state.
export async function appArchiveSession(binding, context, {env=process.env, fetchImpl=fetch}={}) {
  const url = new URL(env.OPENCHAMBER_AGENT_TOOL_URL ?? '');
  require(url.protocol==='http:' && ['127.0.0.1','localhost','[::1]'].includes(url.hostname)
    && url.pathname==='/api/openchamber/agent-tool' && !url.username && !url.password && !url.search && !url.hash,
  'Supported local OpenChamber archive connection required');
  require(env.OPENCHAMBER_AGENT_TOOL_TOKEN, 'Inherited OpenChamber authentication unavailable');
  const response = await fetchImpl(url,{method:'POST',redirect:'error',signal:AbortSignal.timeout(5000),
    headers:{authorization:'Bearer '+env.OPENCHAMBER_AGENT_TOOL_TOKEN,'content-type':'application/json'},
    body:JSON.stringify({tool:'openchamber',sessionID:context.sessionID,callID:context.id,
      input:{action:'session.list',directory:binding.directory,all:true,limit:100}})});
  require(response.ok,'App archive lookup failed');
  const result = await response.json();
  require(result.ok===true && Array.isArray(result.data?.sessions),'App archive state unknown');
  const matches=result.data.sessions.filter(s=>s.id===binding.sessionID);
  require(matches.length===1,'Exact app archive record absent/ambiguous in bounded read');
  const session=matches[0];
  require(session.location?.directory===binding.directory && session.time && Number.isFinite(session.time.created), 'App recipient moved/state unknown');
  require(session.time.archived===undefined,'App recipient archived');
  return session;
}

export function dispatchEligibility(ctx, options, readAttempt, origin, context, connection) {
  require(options && typeof options==='object' && options.fixtureMode===undefined,'Explicit production dispatch policy required');
  require(options.holdBindings && typeof options.holdBindings==='object','Applicable project holds must be bound');
  const holds=projectHolds(options.holdBindings);
  const chief=chiefSelection({chiefPointerFile:options.chiefPointerFile},ctx); // Never forward fixtureMode.
  const lead=recipientEligibility({rosterFile:options.rosterFile,session:ctx.session,
    readAppSession:binding=>appArchiveSession(binding,context,connection)});
  async function originEligible() {
    const current=data(await ctx.session.get({sessionID:origin.sessionID}));
    require(current?.id===origin.sessionID && current.location?.directory===origin.directory && !current.time?.archived,'Native origin moved/archived');
    let chiefAuthorized=false;
    if (options.chiefPointerFile!==undefined) {
      require(path.isAbsolute(options.chiefPointerFile),'Absolute chief pointer required');
      chiefAuthorized=await chief.authorized(origin.sessionID);
    }
    if (!chiefAuthorized) {
      require(path.isAbsolute(options.rosterFile ?? ''),'Enrolled lead roster binding required');
      await lead(origin); // Same unchanged native identity and active roster gate.
    }
    await holds({...origin,...(options.lane===undefined?{}:{lane:options.lane})});
    await appArchiveSession(origin,context,connection);
  }
  return async binding => {
    await originEligible(); // A held origin also fences all its owned workers.
    if (binding.sessionID!==origin.sessionID) {
      const a=await readAttempt(), d=a.host_dispatch;
      require(['admitted','running','uncertain'].includes(a.state) && d && sameOrigin(d.origin,origin)
        && a.session_id===binding.sessionID && d.sessionID===binding.sessionID
        && a.task.directory===binding.directory && d.directory===binding.directory,'Worker not owned by this exact admission/origin');
      const worker=data(await ctx.session.get({sessionID:binding.sessionID}));
      require(worker?.id===binding.sessionID && worker.location?.directory===binding.directory
        && worker.agent===d.agent && !worker.metadata?.openchamber?.goal && !worker.time?.archived,'Worker identity/goal/archive differs');
      await appArchiveSession(binding,context,connection);
    } else require(binding.directory===origin.directory,'Origin directory differs');
    return {sessionID:binding.sessionID,directory:binding.directory,held:false,archived:false};
  };
}
