// Opt-in ONE-CREATE probe. Never invokes the full native suite or retries a create.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
import {OpenCode} from '@opencode/client';

const src=path.dirname(path.dirname(fileURLToPath(import.meta.url))),approved=process.env.CHIEF_NATIVE_TEMP_ROOT;
if (!approved || !path.isAbsolute(approved) || !fs.statSync(approved).isDirectory()) throw Error('explicit approved CHIEF_NATIVE_TEMP_ROOT required');
const root=fs.realpathSync(fs.mkdtempSync(path.join(approved,'single-result-'))),home=path.join(root,'home'),project=path.join(home,'.chiefs/example'),outcome=path.join(project,'outcomes/single-create');
const binary=process.env.CHIEF_OPENCODE_BINARY,a2a=process.env.CHIEF_A2A_ROOT;
if (!binary || !a2a || !path.isAbsolute(binary) || !path.isAbsolute(a2a)) throw Error('set absolute CHIEF_OPENCODE_BINARY and CHIEF_A2A_ROOT');
const callID='result_adapter_create_once',marker='NATIVE_SINGLE_RESULT_CREATE';
for(const name of ['home','tmp','config/opencode','data','state','cache','model'])fs.mkdirSync(path.join(root,name),{recursive:true});
const env={PATH:'/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',HOME:home,TMPDIR:path.join(root,'tmp'),
  CHIEF_A2A_ROOT:a2a,CHIEF_A2A_MODULE:path.join(a2a,'src/plugin.js'),
  XDG_CONFIG_HOME:path.join(root,'config'),XDG_DATA_HOME:path.join(root,'data'),XDG_STATE_HOME:path.join(root,'state'),XDG_CACHE_HOME:path.join(root,'cache'),
  OPENCODE_CONFIG_DIR:path.join(root,'config/opencode'),OPENCODE_DISABLE_MODELS_FETCH:'true',OPENCODE_DISABLE_AUTOUPDATE:'true',DO_NOT_TRACK:'1',
  PYTHONDONTWRITEBYTECODE:'1',NPM_CONFIG_OFFLINE:'true',NPM_CONFIG_UPDATE_NOTIFIER:'false',A2A_STATE_DIR:path.join(root,'a2a'),A2A_PEERS_FILE:path.join(root,'peers.json'),A2A_POLL_MS:'100'};
const save=(name,data)=>fs.writeFileSync(path.join(root,name),JSON.stringify(data,null,2));
const observations=()=>fs.existsSync(path.join(root,'returns.jsonl'))?fs.readFileSync(path.join(root,'returns.jsonl'),'utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[];
let child,model,log,watchdog,tracking,cleaning,eventTask,eventError,streamReady=false,emitted=0,continuation;
const owned=new Map(),captures=[],events=[];const streamAbort=new AbortController();
const deadline=Date.now()+55000;
function options(max=20000){return {signal:AbortSignal.timeout(Math.max(1,Math.min(max,deadline-Date.now())))};}
function processes(){return execFileSync('/bin/ps',['-axo','pid=,ppid=,command='],{encoding:'utf8',timeout:2000}).trim().split('\n').map(line=>{const m=line.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/);return m&&{pid:+m[1],ppid:+m[2],cmd:m[3]};}).filter(Boolean);}
function track(){if(!child)return;const list=processes();let more=true;while(more){more=false;for(const p of list)if((p.ppid===child.pid||owned.has(p.ppid))&&!owned.has(p.pid)){owned.set(p.pid,p);more=true;}}save('pids.json',{harness:process.pid,server:child.pid,children:[...owned.values()]});}
async function cleanup(){if(cleaning)return cleaning;cleaning=(async()=>{
  clearTimeout(watchdog);clearInterval(tracking);streamAbort.abort();
  if(eventTask)await Promise.race([eventTask,new Promise(r=>setTimeout(r,1000))]);
  if(child&&child.exitCode===null){child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),new Promise(r=>setTimeout(r,2000))]);if(child.exitCode===null){child.kill('SIGKILL');await new Promise(r=>child.once('exit',r));}}
  for(const p of processes())if(owned.has(p.pid)&&owned.get(p.pid).cmd===p.cmd){try{process.kill(p.pid,'SIGTERM');}catch{}}
  if(model){model.closeAllConnections();await new Promise(r=>model.close(r));}if(log!==undefined)fs.closeSync(log);
  let listeners='';try{listeners=execFileSync('/usr/sbin/lsof',['-nP','-a','-p',String(process.pid),'-iTCP','-sTCP:LISTEN'],{encoding:'utf8',timeout:2000});}catch(e){if(e.status!==1)throw e;}
  const remaining=processes().filter(p=>p.pid===child?.pid||owned.has(p.pid));save('cleanup.json',{remaining,listeners});assert.equal(remaining.length,0);assert.equal(listeners,'');
})();return cleaning;}
async function until(fn,ms){const end=Math.min(deadline,Date.now()+ms);while(Date.now()<end){if(await fn(end))return;await new Promise(r=>setTimeout(r,30));}throw Error('bounded observation timed out');}
const textOf=message=>typeof message?.content==='string'?message.content:(message?.content||[]).map(p=>p.text||'').join('\n');
try {
  watchdog=setTimeout(()=>{save('watchdog.json',{expired:true,emitted});cleanup().finally(()=>process.exit(2));},55000);
  fs.writeFileSync(path.join(root,'install.log'),execFileSync('/bin/bash',[path.join(src,'install.sh'),'--profile','example'],{env,timeout:15000}));
  fs.mkdirSync(outcome,{recursive:true});
  // Owned fixture instrumentation only. Keep installed guard/config/source pin unchanged.
  const entry=path.join(project,'.opencode/plugins/chief-domain/index.ts'),original=fs.readFileSync(entry,'utf8');
  const match=original.match(/export default makePlugin\((\{.*\})\);/s);assert.ok(match);
  const config=JSON.parse(match[1]);save('policy-config.json',config);
  fs.writeFileSync(entry,original.replace(match[0],`import fs from 'node:fs';\nimport {observeResult} from ${JSON.stringify(new URL('./result-observation.mjs',import.meta.url).href)};\nexport default makePlugin(${match[1]},{observeTransportResult:event=>fs.appendFileSync(${JSON.stringify(path.join(root,'returns.jsonl'))},JSON.stringify(observeResult(event))+'\\n')});`));
  model=createServer(async(req,res)=>{try{
    let raw='';for await(const part of req)raw+=part;const body=JSON.parse(raw);captures.push({url:req.url,body});save('model-captures.json',captures);
    const tools=(body.tools||[]).map(t=>t.function?.name),hasCreate=tools.includes('domain_a2a_create');
    let delta={role:'assistant',content:'Synthetic fixture title.'},finish='stop';
    if(hasCreate){
      for(const name of ['a2a_create','a2a_send','shell','execute','subagent','openchamber'])assert.ok(!tools.includes(name),'forbidden exposure: '+name);
      assert.ok(tools.includes('domain_identity'));assert.ok(tools.includes('domain_a2a_send'));
      const last=body.messages.findLastIndex(m=>m.role==='user');assert.ok(textOf(body.messages[last]).includes(marker));
      if(emitted===0){
        assert.ok(!body.messages.some(m=>m.role==='tool'));emitted++;
        delta={role:'assistant',tool_calls:[{index:0,id:callID,type:'function',function:{name:'domain_a2a_create',arguments:JSON.stringify({server:'local',agent:'example-lead',directory:outcome,model:'fixture/only'})}}]};finish='tool_calls';
      } else {
        const matching=body.messages.slice(last+1).filter(m=>m.role==='tool'&&m.tool_call_id===callID);
        assert.equal(matching.length,1,'exact matching result required; never emit a second create');
        assert.ok(!textOf(matching[0]).includes('Tool result missing'),'compiler fallback is a probe failure');
        const after=observations().find(o=>o.stage==='after');assert.ok(after);
        assert.equal(textOf(matching[0]),after.content,'continuation must receive actual transport content');
        continuation={callID,content:textOf(matching[0]),destination:after.destination};save('continuation.json',continuation);
        delta={role:'assistant',content:'Actual create result received: '+continuation.content};
      }
    }
    res.writeHead(200,{'Content-Type':'text/event-stream'});
    for(const chunk of [{delta,finish_reason:null},{delta:{},finish_reason:finish}])res.write(`data: ${JSON.stringify({id:'fixture',object:'chat.completion.chunk',created:1,model:'only',choices:[{index:0,...chunk}],usage:{prompt_tokens:10,completion_tokens:10,total_tokens:20}})}\n\n`);
    res.end('data: [DONE]\n\n');
  }catch(e){save('provider-error.json',{error:String(e),stack:e.stack,emitted});res.writeHead(400);res.end(String(e));}});
  await new Promise(r=>model.listen(0,'127.0.0.1',r));env.FIXTURE_MODEL_PORT=String(model.address().port);
  const reservation=createServer();await new Promise(r=>reservation.listen(0,'127.0.0.1',r));const port=reservation.address().port;await new Promise(r=>reservation.close(r));
  env.OPENCODE_SERVER_PASSWORD=randomBytes(24).toString('hex');env.OPENCODE_SERVER_USERNAME='opencode';env.A2A_LOCAL_URL=`http://127.0.0.1:${port}`;
  fs.writeFileSync(env.A2A_PEERS_FILE,JSON.stringify({self:{name:'fixture',allowCreate:true,url:env.A2A_LOCAL_URL,passwordEnv:'OPENCODE_SERVER_PASSWORD'},peers:[]}));
  fs.writeFileSync(path.join(root,'model/package.json'),JSON.stringify({name:'single-result-fake-only',type:'module',main:'index.js'}));
  fs.writeFileSync(path.join(root,'model/index.js'),`export default {id:'single-result-fake-only',async setup(ctx){await ctx.provider.transform(editor=>{const template=editor.list().flatMap(p=>[...p.models.values()])[0];if(!template)throw Error('no model template');for(const p of editor.list())editor.remove(p.provider.id);editor.add({info:{id:'fixture',name:'Fake only',activation:'enabled',package:'@opencode/ai/providers/openai/chat',settings:{apiKey:'fixture',baseURL:'http://127.0.0.1:'+process.env.FIXTURE_MODEL_PORT+'/v1'}},models:[{...template,id:'only',modelID:'only',providerID:'fixture',package:'@opencode/ai/providers/openai/chat',status:'active',settings:{},capabilities:{tools:true,input:['text'],output:['text']},enabled:true,variants:[],cost:[],limit:{context:100000,output:10000}}]});});}};`);
  fs.writeFileSync(path.join(root,'config/opencode/opencode.json'),JSON.stringify({model:'fixture/only',plugins:[path.join(root,'model'),a2a]}));
  log=fs.openSync(path.join(root,'server.log'),'w',0o600);
  child=spawn(binary,['serve','--hostname','127.0.0.1','--port',String(port),'--print-logs'],{cwd:project,env,stdio:['ignore',log,log]});
  save('launch.json',{pid:child.pid,args:child.spawnargs,port,modelPort:model.address().port,envKeys:Object.keys(env)});track();tracking=setInterval(track,500);
  const api=OpenCode.make({baseUrl:env.A2A_LOCAL_URL,headers:{Authorization:'Basic '+Buffer.from('opencode:'+env.OPENCODE_SERVER_PASSWORD).toString('base64')}});
  await until(async()=>{try{const version=await api.server.info(options(1000));save('version.json',version);return true;}catch{return false;}},24000);
  eventTask=(async()=>{try{for await(const event of api.event.subscribe({signal:streamAbort.signal,onActivity:()=>{streamReady=true;}})){
    streamReady=true;if(event.type.startsWith('session.')||event.type==='server.connected'){events.push(event);save('events.json',events);}
  }}catch(e){if(!streamAbort.signal.aborted){eventError=String(e);save('event-error.json',{error:eventError});}}})();
  await until(()=>streamReady,3000);
  const chief=await api.session.create({agent:'example-chief',location:{directory:project},model:{providerID:'fixture',id:'only'}},options());save('chief.json',chief);
  const admitted=await api.session.prompt({sessionID:chief.id,text:marker},options());save('admission.json',admitted);
  let context,assistant,part;
  await until(async end=>{
    context=await api.session.context({sessionID:chief.id},{signal:AbortSignal.timeout(Math.max(1,Math.min(2000,end-Date.now())))});save('context.json',context);
    assistant=context.find(m=>(m.content||[]).some(p=>p.type==='tool'&&p.id===callID));part=assistant?.content.find(p=>p.type==='tool'&&p.id===callID);
    return part&&['completed','error','failed','cancelled'].includes(part.state?.status);
  },12000);
  assert.equal(part.state.status,'completed',JSON.stringify(part));assert.equal(part.name,'domain_a2a_create');
  await api.session.wait({sessionID:chief.id},options());await until(()=>!!continuation,3000);
  const observed=observations();assert.equal(observed.length,2);const [before,after]=observed;assert.equal(before.stage,'before');assert.equal(after.stage,'after');
  assert.equal(before.ownParentID,true);assert.equal(before.parentIDType,'undefined');assert.deepEqual(before.metadataIssues,['$.a2a.parentID: undefined']);
  assert.equal(after.ownParentID,false);assert.deepEqual(after.metadataIssues,[]);assert.deepEqual(after.resultIssues,[]);
  for(const observation of observed){assert.equal(observation.callID,callID);assert.equal(observation.messageID,assistant.id);assert.equal(observation.sessionID,chief.id);assert.equal(observation.agent,'example-chief');assert.equal(observation.nested,false);assert.equal(observation.ok,true);assert.ok(observation.contentLength>0);}
  assert.equal(before.content,after.content);assert.equal(before.destination,after.destination);
  assert.equal(part.state.metadata.a2a.to,after.destination);assert.equal(Object.hasOwn(part.state.metadata.a2a,'parentID'),false);
  assert.equal(part.state.content.map(c=>c.text||'').join('\n'),after.content);
  await until(()=>events.some(e=>e.type==='session.tool.success'&&e.data.sessionID===chief.id&&e.data.assistantMessageID===assistant.id&&e.data.id===callID),3000);
  const success=events.filter(e=>e.type==='session.tool.success'&&e.data.sessionID===chief.id&&e.data.assistantMessageID===assistant.id&&e.data.id===callID);assert.equal(success.length,1);assert.ok(success[0].durable);
  assert.equal(success[0].data.metadata.a2a.to,after.destination);assert.ok(!eventError);
  const childID=after.destination.match(/^local\/(ses_[A-Za-z0-9]+)$/)?.[1];assert.ok(childID);
  const childInfo=await api.session.get({sessionID:childID},options()),all=await api.session.list({limit:10},options());
  assert.equal(all.data.length,2);assert.equal(childInfo.agent,'example-lead');assert.equal(childInfo.location.directory,outcome);assert.equal(childInfo.parentID,undefined);
  assert.deepEqual(childInfo.metadata.a2a,{createdBy:'fixture/'+chief.id,parent:'fixture/'+chief.id,nested:false});
  assert.equal((await api.session.context({sessionID:childID},options())).length,0);assert.equal(emitted,1);
  save('proof.json',{status:'PASS',emittedCreates:emitted,sessionCount:all.data.length,chief:chief.id,child:childInfo,callID,assistantMessageID:assistant.id,observed,continuation,success:success[0],goal:'not called',scope:'single nonnested create/result only'});
  console.log('SINGLE CREATE PASS',root);
}catch(e){save('failure.json',{error:String(e),stack:e.stack,emitted,observed:observations()});console.error('SINGLE CREATE FAIL',root,String(e));process.exitCode=1;}
finally{try{await cleanup();}catch(e){save('cleanup-error.json',{error:String(e)});console.error(e);process.exitCode=1;}console.log('CLEANUP',root);}
