// Native V2 hooks; loaded only by the scoped home's local plugin entry.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {loadDirectory, resolveOwner, validateHandoff} from '../../services/directory/local.mjs';
import {leadStartTool} from './lead-start.mjs';
import {boundGoalRequest} from './goal-binding.mjs';
import {adaptA2aResult} from './a2a-result.mjs';

const inside = (root, value) => value === root || value.startsWith(root + path.sep);
const flatten = input => ({...input, ...(input?.parameters || {})});
export function roleFor(config, agent) {
  return ['chief','lead','worker'].find(role => config[role+'_agent'] === agent);
}
export function filterCatalog(config, event) {
  if (!roleFor(config,event.agent)) {
    for (const name of ['domain_identity','domain_a2a_create','domain_a2a_send','domain_lead_start']) delete event.tools[name];
    return;
  }
  // Deny Code Mode entirely: no hidden inherited namespace/session controller can survive.
  const allowed = new Set(['read','write','edit','patch','skill','webfetch','websearch','domain_a2a_send','domain_identity']);
  if (roleFor(config,event.agent) !== 'worker') allowed.add('domain_a2a_create');
   if (roleFor(config,event.agent) !== 'worker') allowed.add('domain_lead_start');
  for (const name of Object.keys(event.tools)) if (!allowed.has(name)) delete event.tools[name];
}
export function canEdit(config, role, location, resource) {
  const target = path.resolve(location,resource);
  if (!inside(config.home,location) || !inside(config.home,target)) return false;
  let current=config.home;
  for (const part of path.relative(config.home,target).split(path.sep)) {
    current=path.join(current,part);
    try { if (fs.lstatSync(current).isSymbolicLink()) return false; }
    catch (e) { if (e.code!=='ENOENT') return false; }
  }
  const relative = path.relative(config.home,target).split(path.sep);
  const managed=[path.join(config.home,'AGENTS.md'),...(config.managed_paths||[])];
  if (managed.some(p=>p.toLowerCase()===target.toLowerCase()) || relative.some(x => x.toLowerCase() === '.opencode' || x.toLowerCase().startsWith('.kit-'))) return false;
  if (role === 'chief') return true;
  if (!inside(path.join(config.home,'outcomes'),location)) return false;
  if (role === 'lead') return target === path.join(location,'LEAD.md') || inside(path.join(location,'lead'),target);
  return inside(path.join(location,'output'),target) || inside(path.join(location,'notes'),target);
}
function canonicalLocation(session) {
  const directory = session?.location?.directory;
  if (typeof directory !== 'string' || !path.isAbsolute(directory)) throw Error('session location unavailable');
  return fs.realpathSync(directory);
}
export function makePlugin(config, {goalRequest,observeTransportResult}={}) {
  return {id:'chief-domain-'+config.id, async setup(ctx) {
    const source=fileURLToPath(config.transport_module);
    const fingerprint=()=>createHash('sha256').update(fs.readFileSync(source)).digest('hex');
    if (fingerprint()!==config.transport_sha256) throw Error('a2a source changed; reinstall/review before capture');
    // _tools builds descriptors/closures only. No _sharedState/setup/start or new transport.
    const canonical=new Map((await import(config.transport_module))._tools(undefined).map(t=>[t.name,t]));
    const captured=new Map();
    async function captureTransport(name) {
      if (fingerprint()!==config.transport_sha256) throw Error('a2a source changed; review before dispatch');
      if (captured.has(name)) return captured.get(name);
      // Local plugins can load before global transport. Resolve this fixed name
      // on first invocation, after catalogs settle, and pin its callable capability.
      const expected=canonical.get(name), tool=(await ctx.tool.list()).find(t=>t.id===name);
      if (!expected || !tool || tool.description!==expected.description || tool.options?.codemode!==false || typeof tool.execute!=='function') throw Error('expected a2a transport unavailable/replaced at capture');
      captured.set(name,tool.execute);
      return tool.execute;
    }
    for (const kind of ['context','generate','compaction']) await ctx.session.hook(kind,event=>filterCatalog(config,event));
    await ctx.permission.hook('evaluate',async event=>{
      const role=roleFor(config,event.agent);
      if (!role || event.action !== 'edit') return;
      const current=await ctx.session.get({sessionID:event.sessionID});
      if (!event.resources.every(r=>canEdit(config,role,canonicalLocation(current),r))) {
        event.effect='deny';event.message='outside this domain role memory boundary';
      }
    });
    await ctx.tool.transform(editor=>{
      editor.add({name:'domain_identity',options:{codemode:false},
        description:'Return your own session id and scoped domain; no contact or state changes.',
        input:{type:'object',properties:{},additionalProperties:false},
        execute:async (_input,c)=>{
          if (!roleFor(config,c.agent)) throw Error('not a scoped agent');
          const caller=await ctx.session.get({sessionID:c.sessionID});
          if (caller.agent!==c.agent || !inside(config.home,canonicalLocation(caller)) || caller.time?.archived) throw Error('scoped identity mismatch');
          return {content:JSON.stringify({session:c.sessionID,domain:config.id,home:config.home})};
        }});
      editor.add(leadStartTool(ctx,config,goalRequest ?? boundGoalRequest(ctx,config)));
      for (const toolName of ['a2a_create','a2a_send']) {
        const expected=canonical.get(toolName), guarded='domain_'+toolName;
        if (!expected) throw Error('canonical transport descriptor missing');
        editor.add({name:guarded,description:'Scoped guarded existing transport: '+expected.description,
          input:expected.input,options:{codemode:false},execute:async (raw,c)=>{
          const role=roleFor(config,c.agent);
          if (!role) throw Error('guarded transport requires a scoped role');
          const input=flatten(raw);
          const caller=await ctx.session.get({sessionID:c.sessionID});
          const location=canonicalLocation(caller);
          if (!inside(config.home,location) || caller.agent !== c.agent || caller.time?.archived) throw Error('scoped session mismatch');
          if (toolName === 'a2a_create') {
            const next=role === 'chief' ? config.lead_agent : role === 'lead' ? config.worker_agent : null;
            if (!next || input.server !== 'local') throw Error('unscoped delegation refused');
            const directory=input.directory ? fs.realpathSync(input.directory) : location;
            const fresh=input.agent===config[role+'_agent'] && input.nest===false && directory===location;
            if (!fresh && (input.agent!==next || !inside(path.join(config.home,'outcomes'),directory) || (role==='lead' && (directory!==location || input.nest===false)))) throw Error('unscoped outcome directory or agent');
          } else {
            if (input.create) throw Error('send-with-create bypass refused');
            const match=/^(?:local\/)?(ses_[A-Za-z0-9]+)$/.exec(input.to||'');
            if (!match) throw Error('local explicit session address required');
            const target=await ctx.session.get({sessionID:match[1]});
            if (target.time?.archived) throw Error('archived target');
            const targetDir=canonicalLocation(target);
            const ownTarget=role==='chief' && target.agent===config.lead_agent && inside(path.join(config.home,'outcomes'),targetDir)
              || role==='lead' && target.agent===config.worker_agent && targetDir===location
              || role==='worker' && target.agent===config.lead_agent && targetDir===location
              || role!=='worker' && target.agent===c.agent && targetDir===location && typeof target.metadata?.a2a?.createdBy==='string' && target.metadata.a2a.createdBy.endsWith('/'+c.sessionID);
            if (!ownTarget) {
              if (role==='worker') throw Error('workers report only to their outcome lead');
              const rows=loadDirectory(config.directory).domains;
              const row=rows.find(r=>{ try {return resolveOwner(config.directory,r.id).session===match[1];} catch {return false;} });
              if (!row || targetDir!==row.home || (role!=='chief' && row.id!==config.id)) throw Error('not a live reporting owner');
              const ownerAgent=row.id===config.id ? config.chief_agent : row.id==='technical' ? 'chief-of-staff'
                : JSON.parse(fs.readFileSync(path.join(row.home,'.kit-install.json'),'utf8')).identity.chief_agent;
              if (target.agent!==ownerAgent) throw Error('owner agent mismatch');
              if (row.id!==config.id) {
                const envelope=validateHandoff(JSON.parse(input.text));
                if (envelope.owner!==row.id || envelope.origin.domain!==config.id || envelope.origin.session!==c.sessionID) throw Error('unattributed handoff');
                if (input.expectReply===false) throw Error('handoff needs automatic receipt');
              }
            }
          }
          const original=await captureTransport(toolName);
          const rawResult=await original(raw,c); // Same existing transport/context.
          observeTransportResult?.({stage:'before',result:rawResult,context:c,tool:guarded});
          const result=adaptA2aResult(rawResult);
          observeTransportResult?.({stage:'after',result,context:c,tool:guarded});
          return result;
        }});
      }
    });
  }};
}
