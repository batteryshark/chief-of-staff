// Narrow create surface. Production supplies the optional operator-owned host binding.
import fs from 'node:fs';
import path from 'node:path';
import {isConcreteModel} from './goal-binding.mjs';

export function controlRequester(url, authorization, fetchImpl=fetch) {
  // Low-level contract-test seam; NOT used by the generated/runtime plugin binding.
  const endpoint=new URL(url);
  if (endpoint.protocol!=='http:' || endpoint.hostname!=='127.0.0.1' || !endpoint.port || endpoint.pathname!=='/api/openchamber/control' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) throw Error('explicit loopback OpenChamber control endpoint required');
  if (typeof authorization!=='string' || !authorization.trim()) throw Error('explicit control authorization required');
  return async input=>{
    const response=await fetchImpl(endpoint,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json',Authorization:authorization},
      body:JSON.stringify({action:'session.create',input}),signal:AbortSignal.timeout(20000)});
    const result=await response.json();
    if (!response.ok) throw Error('goal dispatch uncertain/failed; reconcile, do not blindly retry');
    return result;
  };
}

export function leadStartTool(ctx,config,request) {
  return {name:'domain_lead_start',description:'Chief starts only its configured goal lead; that confirmed lead may explicitly replace itself in the SAME outcome with replacement:true. Requires an optional operator binding. Uncertain dispatch requires operator reconciliation, never replay. No a2a goal flags.',
    options:{codemode:false},input:{type:'object',properties:{directory:{type:'string'},objective:{type:'string'},model:{type:'string'},replacement:{type:'boolean'}},required:['directory','objective','model'],additionalProperties:false},
    execute:async (input,c)=>{
      if (!isConcreteModel(input?.model)) throw Error('concrete explicit model required; Auto routing refused');
      const replacement=c.agent===config.lead_agent && input?.replacement===true;
      if (c.agent!==config.chief_agent && !replacement) throw Error('only this domain chief or explicitly replacing lead starts goal leads');
      const caller=await ctx.session.get({sessionID:c.sessionID});
      if (caller.agent!==c.agent || caller.time?.archived || (!replacement && fs.realpathSync(caller.location.directory)!==config.home)) throw Error('chief identity/location mismatch');
      if (!input || Object.keys(input).some(k=>!['directory','objective','model','replacement'].includes(k)) || (input.replacement!==undefined && input.replacement!==replacement) || typeof input.objective!=='string' || !input.objective.trim() || input.objective.length>16000) throw Error('bounded goal objective/model required');
      const directory=fs.realpathSync(input.directory),root=path.join(config.home,'outcomes');
      if (!directory.startsWith(root+path.sep)) throw Error('goal lead must own a specific scoped outcome');
      if (!fs.statSync(directory).isDirectory()) throw Error('outcome must be an existing directory');
      if (replacement && fs.realpathSync(caller.location.directory)!==directory) throw Error('replacement must retain own outcome');
      if (fs.realpathSync(root)!==root || path.resolve(input.directory)!==directory) throw Error('linked outcome refused');
      if (typeof request!=='function') throw Error('goal bridge not configured; no goal was activated');
      // Exact installed CLI session-create payload; no caller-selected action/agent/options.
      const payload={directory,agent:config.lead_agent,title:'[lead] '+path.basename(directory),
        prompt:'Goal: '+input.objective,model:input.model,goal:true,wait:false,lastAssistant:false};
      const result=await request(payload,{sessionID:c.sessionID,replacement});
      if (result?.goalEnabled!==true || result.promptDispatched!==true || !/^ses_[A-Za-z0-9]+$/.test(result.sessionId||'') || result.directory!==directory) throw Error('goal not confirmed; reconcile partial result, do not retry');
      const lead=await ctx.session.get({sessionID:result.sessionId});
      const slash=input.model.indexOf('/');
      if (lead.agent!==config.lead_agent || lead.time?.archived || fs.realpathSync(lead.location.directory)!==directory ||
          lead.model?.providerID!==input.model.slice(0,slash) || lead.model?.id!==input.model.slice(slash+1)) throw Error('created goal lead identity mismatch; reconcile');
      return {content:JSON.stringify({sessionId:result.sessionId,directory,goalEnabled:true})};
    }};
}
