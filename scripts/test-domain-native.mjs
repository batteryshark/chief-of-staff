// Explicit opt-in native regression. NOT included in npm/direct offline discovery.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
import {OpenCode} from '@opencode/client';

const src=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const approved=process.env.CHIEF_NATIVE_TEMP_ROOT;
if (!approved || !path.isAbsolute(approved) || !fs.statSync(approved).isDirectory()) throw Error('set CHIEF_NATIVE_TEMP_ROOT to an approved existing scratch directory');
const root=fs.realpathSync(fs.mkdtempSync(path.join(approved,'domain-native-'))),home=path.join(root,'home'),project=path.join(home,'.chiefs/example'),tech=path.join(home,'.chief-of-staff'),outcome=path.join(project,'outcomes/study');
const binary=process.env.CHIEF_OPENCODE_BINARY,a2a=process.env.CHIEF_A2A_ROOT;
if (!binary || !a2a || !path.isAbsolute(binary) || !path.isAbsolute(a2a)) throw Error('set absolute CHIEF_OPENCODE_BINARY and CHIEF_A2A_ROOT');
for(const d of ['home','tmp','config/opencode','data','state','cache','model'])fs.mkdirSync(path.join(root,d),{recursive:true});
// Allowlist: no inherited URLs/session IDs/config content/provider auth/real peers.
const env={PATH:'/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',HOME:home,TMPDIR:path.join(root,'tmp'),
  CHIEF_A2A_ROOT:a2a,CHIEF_A2A_MODULE:path.join(a2a,'src/plugin.js'),
  XDG_CONFIG_HOME:path.join(root,'config'),XDG_DATA_HOME:path.join(root,'data'),XDG_STATE_HOME:path.join(root,'state'),XDG_CACHE_HOME:path.join(root,'cache'),
  OPENCODE_CONFIG_DIR:path.join(root,'config/opencode'),OPENCODE_DISABLE_MODELS_FETCH:'true',OPENCODE_DISABLE_AUTOUPDATE:'true',DO_NOT_TRACK:'1',
  PYTHONDONTWRITEBYTECODE:'1',NPM_CONFIG_OFFLINE:'true',NPM_CONFIG_UPDATE_NOTIFIER:'false',
  A2A_STATE_DIR:path.join(root,'a2a'),A2A_PEERS_FILE:path.join(root,'peers.json'),A2A_POLL_MS:'100'};
fs.writeFileSync(path.join(root,'install.log'),execFileSync('/bin/bash',[path.join(src,'install.sh'),'--profile','example'],{env,timeout:20000}));
fs.mkdirSync(outcome,{recursive:true});fs.mkdirSync(tech,{recursive:true});fs.writeFileSync(path.join(tech,'models.md'),'Synthetic fixture only.');
const captures=[],results=[],actions=new Map(),handoffs=new Map(),owned=new Map();let child,log,tracking,watchdog,model,api,cleaning;
const save=(name,value)=>fs.writeFileSync(path.join(root,name),JSON.stringify(value,null,2));
function processes(){return execFileSync('/bin/ps',['-axo','pid=,ppid=,command='],{encoding:'utf8',timeout:2000}).trim().split('\n').map(l=>{const m=l.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/);return m&&{pid:+m[1],ppid:+m[2],cmd:m[3]};}).filter(Boolean);}
function track(){if(!child)return;const list=processes();let more=true;while(more){more=false;for(const p of list)if((p.ppid===child.pid||owned.has(p.ppid))&&!owned.has(p.pid)){owned.set(p.pid,p);more=true;}}save('pids.json',{harness:process.pid,server:child.pid,children:[...owned.values()]});}
async function cleanup(){if(cleaning)return cleaning;cleaning=(async()=>{
  clearInterval(tracking);clearTimeout(watchdog);
  if(child&&child.exitCode===null){child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),new Promise(r=>setTimeout(r,3000))]);if(child.exitCode===null){child.kill('SIGKILL');await new Promise(r=>child.once('exit',r));}}
  // Parent first; only still-owned exact PID/command descendants, never broad kills.
  for(const p of processes())if(owned.has(p.pid)&&owned.get(p.pid).cmd===p.cmd){try{process.kill(p.pid,'SIGTERM');}catch{}}
  if(model){model.closeAllConnections();await new Promise(r=>model.close(r));}if(log!==undefined)fs.closeSync(log);
  let listeners='';try{listeners=execFileSync('/usr/sbin/lsof',['-nP','-a','-p',String(process.pid),'-iTCP','-sTCP:LISTEN'],{encoding:'utf8',timeout:2000});}catch(e){if(e.status!==1)throw e;}
  const remaining=processes().filter(p=>p.pid===child?.pid||owned.has(p.pid));save('cleanup.json',{remaining,listeners});assert.equal(remaining.length,0);assert.equal(listeners,'');
})();return cleaning;}
async function call(label,fn){const value=await fn({signal:AbortSignal.timeout(20000)});results.push({label,result:value});save('results.json',results);return value;}
const textOf=m=>typeof m?.content==='string'?m.content:(m?.content||[]).map(p=>p.text||'').join('\n');
const toolParts=context=>context.flatMap(m=>m.content||[]).filter(p=>p.type==='tool');
async function probe(session,label,name,args){const token='NATIVE_STEP_'+actions.size;actions.set(token,{name,args,session:session.id,label});
  await call(label+' prompt',o=>api.session.prompt({sessionID:session.id,text:token},o));await call(label+' wait',o=>api.session.wait({sessionID:session.id},o));
  const deadline=Date.now()+12000;let context,part;
  while(Date.now()<deadline){
    context=await api.session.context({sessionID:session.id},{signal:AbortSignal.timeout(Math.max(1,Math.min(2000,deadline-Date.now())))});
    part=toolParts(context).filter(t=>t.name===name).at(-1);
    if(part&&['completed','error','failed','cancelled'].includes(part.state?.status)){
      results.push({label:label+' terminal context',result:context});save('results.json',results);return part;
    }
    await new Promise(r=>setTimeout(r,Math.min(50,Math.max(1,deadline-Date.now()))));
  }
  save('nonterminal.json',{label,part,context});throw Error('tool did not reach terminal state within 12s: '+label);
}
function complete(part){assert.equal(part?.state?.status,'completed',JSON.stringify(part));return part.state;}
const toolText=part=>(part.state?.content||[]).map(p=>p.text||'').join('\n');
async function until(fn,ms=12000){const start=Date.now();while(Date.now()-start<ms){if(await fn())return;await new Promise(r=>setTimeout(r,100));}throw Error('bounded fixture observation timed out');}
const pointer=(directory,session)=>fs.writeFileSync(path.join(directory,'chief.json'),JSON.stringify({session,directory,updated:new Date(Date.now()-48*3600000).toISOString()}));
try {
  watchdog=setTimeout(()=>{save('watchdog.json',{expired:true});cleanup().finally(()=>process.exit(2));},175000);
  model=createServer(async(req,res)=>{try{
    let raw='';for await(const c of req)raw+=c;const body=JSON.parse(raw);captures.push({url:req.url,body});save('model-captures.json',captures);
    const last=body.messages.findLastIndex(m=>m.role==='user'),text=textOf(body.messages[last]),finished=body.messages.slice(last+1).some(m=>m.role==='tool');
    let action;
    if(!finished){for(const [token,a]of actions)if(text.includes(token))action=a;
      if(JSON.stringify(body.messages.filter(m=>m.role==='system')).includes('TECHNICAL_FIXTURE_RECEIVER'))for(const [id,envelope]of handoffs)if(text.includes(id))action={name:'fixture_receive',args:{envelope}};}
    const delta=action?{role:'assistant',tool_calls:[{index:0,id:'call_'+captures.length,type:'function',function:{name:action.name,arguments:JSON.stringify(action.args)}}]}:{role:'assistant',content:'Fixture complete.'};
    // Receiver final text is the real owner-local receipt, returned on existing automatic a2a reply.
    if(!action&&finished&&JSON.stringify(body.messages).includes('TECHNICAL_FIXTURE_RECEIVER')){
      const receipt=path.join(tech,'handoffs.json');if(fs.existsSync(receipt))delta.content='AUTOMATIC_RECEIPT '+fs.readFileSync(receipt,'utf8');}
    res.writeHead(200,{'Content-Type':'text/event-stream'});for(const c of [{delta,finish_reason:null},{delta:{},finish_reason:action?'tool_calls':'stop'}])res.write(`data: ${JSON.stringify({id:'fixture',object:'chat.completion.chunk',created:1,model:'only',choices:[{index:0,...c}],usage:{prompt_tokens:10,completion_tokens:10,total_tokens:20}})}\n\n`);res.end('data: [DONE]\n\n');
  }catch(e){res.writeHead(500);res.end(String(e));}});
  await new Promise(r=>model.listen(0,'127.0.0.1',r));env.FIXTURE_MODEL_PORT=String(model.address().port);
  const reservation=createServer();await new Promise(r=>reservation.listen(0,'127.0.0.1',r));const port=reservation.address().port;await new Promise(r=>reservation.close(r));
  env.OPENCODE_SERVER_PASSWORD=randomBytes(24).toString('hex');env.OPENCODE_SERVER_USERNAME='opencode';env.A2A_LOCAL_URL=`http://127.0.0.1:${port}`;
  fs.writeFileSync(env.A2A_PEERS_FILE,JSON.stringify({self:{name:'fixture',allowCreate:true,url:env.A2A_LOCAL_URL,passwordEnv:'OPENCODE_SERVER_PASSWORD'},peers:[]}));
  fs.writeFileSync(path.join(root,'model/package.json'),JSON.stringify({name:'domain-native-fake-only',type:'module',main:'index.js'}));
  fs.writeFileSync(path.join(root,'model/index.js'),`import fs from 'node:fs';import {receiveHandoff,resolveOwner} from ${JSON.stringify(new URL('../services/directory/local.mjs',import.meta.url).href)};
export default {id:'domain-native-fake-only',async setup(ctx){await ctx.provider.transform(editor=>{const template=editor.list().flatMap(p=>[...p.models.values()])[0];if(!template)throw Error('no template');for(const p of editor.list())editor.remove(p.provider.id);editor.add({info:{id:'fixture',name:'Fake only',activation:'enabled',package:'@opencode/ai/providers/openai/chat',settings:{apiKey:'fixture',baseURL:'http://127.0.0.1:'+process.env.FIXTURE_MODEL_PORT+'/v1'}},models:[{...template,id:'only',modelID:'only',providerID:'fixture',package:'@opencode/ai/providers/openai/chat',status:'active',settings:{},capabilities:{tools:true,input:['text'],output:['text']},enabled:true,variants:[],cost:[],limit:{context:100000,output:10000}}]});});
await ctx.tool.transform(editor=>editor.add({name:'fixture_receive',options:{codemode:false},description:'Owned synthetic receiver only.',input:{type:'object',properties:{envelope:{type:'object',additionalProperties:true}},required:['envelope']},execute:async({envelope},c)=>{const owner=resolveOwner(${JSON.stringify(path.join(home,'.config/chief-of-staff/domains.json'))},'technical');const me=await ctx.session.get({sessionID:c.sessionID});if(c.agent!=='chief-of-staff'||owner.session!==c.sessionID||me.agent!==c.agent||me.location.directory!==${JSON.stringify(tech)})throw Error('not fixture technical receiver');return{content:JSON.stringify(receiveHandoff(${JSON.stringify(path.join(home,'.config/chief-of-staff/domains.json'))},'technical',${JSON.stringify(tech)},envelope))};}}));}};`);
  fs.writeFileSync(path.join(root,'config/opencode/opencode.json'),JSON.stringify({model:'fixture/only',plugins:[path.join(root,'model'),a2a],agents:{'chief-of-staff':{system:'TECHNICAL_FIXTURE_RECEIVER. Synthetic data only; return receipt, no new send.',permissions:[{action:'fixture_receive',resource:'*',effect:'allow'}]}}}));
  log=fs.openSync(path.join(root,'server.log'),'w',0o600);
  child=spawn(binary,['serve','--hostname','127.0.0.1','--port',String(port),'--print-logs'],{cwd:project,env,stdio:['ignore',log,log]});
  save('launch.json',{pid:child.pid,args:child.spawnargs,port,modelPort:model.address().port,envKeys:Object.keys(env)});track();tracking=setInterval(track,500);
  api=OpenCode.make({baseUrl:env.A2A_LOCAL_URL,headers:{Authorization:'Basic '+Buffer.from('opencode:'+env.OPENCODE_SERVER_PASSWORD).toString('base64')}});
  const start=Date.now();let info;while(Date.now()-start<24000){try{info=await api.server.info({signal:AbortSignal.timeout(1000)});break;}catch{await new Promise(r=>setTimeout(r,200));}}if(!info)throw Error('startup exceeded 24s');save('version.json',info);
  const create=(agent,directory)=>call('create '+agent,o=>api.session.create({agent,location:{directory},model:{providerID:'fixture',id:'only'}},o));
  const chief=await create('example-chief',project);pointer(project,chief.id);
  let part=await probe(chief,'chief identity','domain_identity',{});complete(part);assert.equal(JSON.parse(toolText(part)).session,chief.id);
  part=await probe(chief,'create lead','domain_a2a_create',{server:'local',agent:'example-lead',directory:outcome,model:'fixture/only'});complete(part);
  const leadId=part.state.metadata.a2a.to.split('/')[1],lead=await call('read created lead',o=>api.session.get({sessionID:leadId},o));assert.equal(lead.agent,'example-lead');assert.equal(lead.location.directory,outcome);assert.equal(lead.parentID,undefined);
  part=await probe(lead,'lead identity','domain_identity',{});complete(part);assert.equal(JSON.parse(toolText(part)).session,lead.id);
  part=await probe(lead,'create worker','domain_a2a_create',{server:'local',agent:'example-worker',model:'fixture/only'});complete(part);
  const workerId=part.state.metadata.a2a.to.split('/')[1],worker=await call('read created worker',o=>api.session.get({sessionID:workerId},o));assert.equal(worker.agent,'example-worker');assert.equal(worker.parentID,lead.id);assert.equal(worker.location.directory,outcome);
  part=await probe(worker,'worker identity','domain_identity',{});complete(part);assert.equal(JSON.parse(toolText(part)).session,worker.id);
  for(const [file,allowed]of [[path.join(project,'probe.md'),true],[path.join(project,'AGENTS.md'),false],[path.join(project,'.opencode/forbidden.md'),false],[path.join(tech,'foreign.md'),false]]){
    const before=fs.existsSync(file)?fs.readFileSync(file,'utf8'):null;
    part=await probe(chief,'write '+path.basename(file),'write',{path:file,content:'Synthetic native note'});
    if(allowed){complete(part);assert.equal(fs.readFileSync(file,'utf8'),'Synthetic native note');}else{assert.notEqual(part.state.status,'completed');assert.equal(fs.existsSync(file)?fs.readFileSync(file,'utf8'):null,before);}}
  part=await probe(chief,'forbidden arbitrary agent','domain_a2a_create',{server:'local',agent:'build',directory:outcome});assert.notEqual(part.state.status,'completed');
  part=await probe(chief,'forbidden foreign directory','domain_a2a_create',{server:'local',agent:'example-lead',directory:tech});assert.notEqual(part.state.status,'completed');
  part=await probe(chief,'forbidden send create','domain_a2a_send',{to:'local/'+lead.id,text:'none',create:{agent:'build'}});assert.notEqual(part.state.status,'completed');
  const technical=await create('chief-of-staff',tech);pointer(tech,technical.id);
  const envelope={version:1,id:'native-synthetic-1',origin:{domain:'example',session:chief.id},owner:'technical',action:'record-idea',principal_attribution:'NATIVE_SYNTHETIC_FIXTURE_ONLY',content:'A synthetic regression idea, never real principal content.'};handoffs.set(envelope.id,envelope);
  const autoCount=context=>context.filter(m=>m.type==='user'&&m.text?.includes('AUTOMATIC_RECEIPT')).length;
  const send=async target=>{const before=autoCount(await api.session.context({sessionID:chief.id},{signal:AbortSignal.timeout(20000)}));
    const p=await probe(chief,'handoff','domain_a2a_send',{to:'local/'+target,text:JSON.stringify(envelope),expectReply:true});complete(p);assert.equal(p.state.metadata.a2a.replyPending,true);
    await until(async()=>autoCount(await api.session.context({sessionID:chief.id},{signal:AbortSignal.timeout(20000)}))>before);
    await call('chief automatic reply idle',o=>api.session.wait({sessionID:chief.id},o));};
  await send(technical.id);
  await until(()=>fs.existsSync(path.join(tech,'handoffs.json')));
  await until(async()=>JSON.stringify(await api.session.context({sessionID:chief.id},{signal:AbortSignal.timeout(20000)})).includes('AUTOMATIC_RECEIPT'));
  await send(technical.id);await call('receiver duplicate idle',o=>api.session.wait({sessionID:technical.id},o));
  const rotated=await create('chief-of-staff',tech);pointer(tech,rotated.id);
  part=await probe(chief,'old rotated owner rejected','domain_a2a_send',{to:'local/'+technical.id,text:JSON.stringify(envelope)});assert.notEqual(part.state.status,'completed');
  await send(rotated.id);await call('rotated receiver idle',o=>api.session.wait({sessionID:rotated.id},o));
  assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(tech,'handoffs.json')))).length,1);
  assert.equal((fs.readFileSync(path.join(tech,'ideas.md'),'utf8').match(/<!-- handoff:/g)||[]).length,1);
  part=await probe(chief,'fresh chief create','domain_a2a_create',{server:'local',agent:'example-chief',directory:project,nest:false,model:'fixture/only'});complete(part);
  const fresh=part.state.metadata.a2a.to.split('/')[1];part=await probe(chief,'fresh same-role handover','domain_a2a_send',{to:'local/'+fresh,text:'Synthetic continuing chief: read fixture state only.',expectReply:true});complete(part);await call('fresh receiver idle',o=>api.session.wait({sessionID:fresh},o));
  const control=await create('build',project);await probe(control,'default catalog','read',{path:path.join(project,'probe.md')});
  const catalogs=captures.map(c=>({system:JSON.stringify(c.body.messages.filter(m=>m.role==='system')),tools:(c.body.tools||[]).map(t=>t.function?.name),user:textOf(c.body.messages.findLast(m=>m.role==='user'))}));
  for(const [session,label,createAllowed]of [[chief,'chief',true],[lead,'lead',true],[worker,'worker',false]]){
    const entry=catalogs.find(c=>c.user.includes([...actions].find(([,a])=>a.name==='domain_identity'&&a.session===session.id)?.[0]||'never'));
    assert.ok(entry,label+' native catalog');assert.ok(entry.tools.includes('domain_identity'));
    assert.ok(entry.tools.includes('domain_a2a_send'));assert.equal(entry.tools.includes('domain_a2a_create'),createAllowed);
  }
  const identityCatalogs=captures.filter(c=>c.body.tools?.some(t=>t.function?.name==='domain_identity'));
  assert.ok(identityCatalogs.some(c=>c.body.tools.some(t=>t.function?.name==='domain_a2a_create')));
  assert.ok(identityCatalogs.some(c=>!c.body.tools.some(t=>t.function?.name==='domain_a2a_create')));
  for(const c of identityCatalogs)for(const name of ['a2a_send','a2a_create','execute','shell','subagent','openchamber'])assert.ok(!c.body.tools.some(t=>t.function?.name===name));
  const defaultCatalog=captures.find(c=>c.body.tools?.some(t=>t.function?.name==='a2a_create'));assert.ok(defaultCatalog);assert.ok(defaultCatalog.body.tools.some(t=>t.function?.name==='execute'));assert.ok(!defaultCatalog.body.tools.some(t=>t.function?.name==='domain_identity'));
  save('proof.json',{chief:chief.id,lead:lead.id,worker:worker.id,workerParent:worker.parentID,technical:technical.id,rotated:rotated.id,fresh,receipts:JSON.parse(fs.readFileSync(path.join(tech,'handoffs.json'))),catalogs,goal:'not activated; real OpenChamber bridge intentionally unbound'});
  console.log('NATIVE PASS',root);
}catch(e){save('fatal.json',{error:String(e),stack:e.stack});console.error('NATIVE FAIL',root,String(e));process.exitCode=1;}
finally{try{await cleanup();}catch(e){save('cleanup-error.json',{error:String(e)});console.error(e);process.exitCode=1;}console.log('CLEANUP',root);}
