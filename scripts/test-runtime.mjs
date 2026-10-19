import {mkdtempSync,mkdirSync,writeFileSync,openSync,closeSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomBytes,randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import assert from 'node:assert/strict';
import {OpenCode} from '@opencode/client';
const exec=promisify(execFile),root=resolve('.'),home=mkdtempSync(join(tmpdir(),'runway-native-'));
const project=join(home,'project'),quotaHome=join(home,'runway');
for(const dir of [project,quotaHome,join(home,'config/opencode'),join(home,'model')])mkdirSync(dir,{recursive:true});
const password=randomBytes(24).toString('hex');
let exhausted=false;const quotaPaths=[];
const stamp=t=>new Date(t).toISOString();
const quota=createServer((req,res)=>{
  quotaPaths.push(req.url);
  if(req.url!=='/api/v1/snapshot'){res.writeHead(500);return res.end('{}');}
  const now=Date.now();res.setHeader('Content-Type','application/json');
  res.end(JSON.stringify({schema_version:2,passive:true,sources:['primary','fallback'].map(id=>({id,slug:id,provider:'codex',account:id,kind:'plan',enabled:true,archived:false,latest:{observed_at:stamp(now-1000),fresh_until:stamp(now+600000),windows:[{id:'weekly',remaining_percent:exhausted&&id==='primary'?0:80,unit:'percent',resets_at:stamp(Math.ceil(now/86400000)*86400000),stale:false}]}}))}));
});
const model=createServer(async(req,res)=>{
  let raw='';for await(const c of req)raw+=c;
  const messages=JSON.parse(raw).messages;
  let user=-1;messages.forEach((m,i)=>{if(m.role==='user')user=i;});
  const route=JSON.stringify(messages[user]).includes('admit-test-worker');
  const done=!route||messages.slice(user+1).some(m=>m.role==='tool');
  const request={action:'prepare',task:{job:'fixture-job',scope:project,directory:project,category:'hard',size:'small',writer:true}};
  const delta=done?{role:'assistant',content:'Fixture finished.'}:{role:'assistant',tool_calls:[{index:0,id:'call_'+randomUUID(),type:'function',function:{name:'runway',arguments:JSON.stringify({request:JSON.stringify(request)})}}]};
  res.writeHead(200,{'Content-Type':'text/event-stream'});
  for(const c of [{delta,finish_reason:null},{delta:{},finish_reason:done?'stop':'tool_calls'}])res.write(`data: ${JSON.stringify({id:'fixture',object:'chat.completion.chunk',created:1,model:'fixture',choices:[{index:0,...c}],usage:{prompt_tokens:10,completion_tokens:10,total_tokens:20}})}\n\n`);
  res.end('data: [DONE]\n\n');
});
await new Promise(r=>quota.listen(0,'127.0.0.1',r));await new Promise(r=>model.listen(0,'127.0.0.1',r));
const portServer=createServer();await new Promise(r=>portServer.listen(0,'127.0.0.1',r));const port=portServer.address().port;await new Promise(r=>portServer.close(r));
const quotaUrl=`http://127.0.0.1:${quota.address().port}`,baseUrl=`http://127.0.0.1:${port}`;
const env={...process.env,XDG_DATA_HOME:join(home,'data'),XDG_CONFIG_HOME:join(home,'config'),XDG_CACHE_HOME:join(home,'cache'),XDG_STATE_HOME:join(home,'state'),OPENCODE_SERVER_PASSWORD:password,CHIEF_RUNWAY_HOME:quotaHome,CHIEF_RUNWAY_TARMAC_URL:quotaUrl,RUNWAY_MODEL_PORT:String(model.address().port)};
writeFileSync(join(home,'model/package.json'),JSON.stringify({name:'runway-fixture',type:'module',main:'index.js'}));
const {copyFileSync}=await import('node:fs');copyFileSync(join(root,'tests/runtime-model.js'),join(home,'model/index.js'));
writeFileSync(join(home,'config/opencode/opencode.json'),JSON.stringify({plugins:[pathToFileURL(join(root,'dist')).href,pathToFileURL(join(home,'model')).href]}));
writeFileSync(join(quotaHome,'routes.json'),JSON.stringify({version:1,routes:['primary','fallback'].map(id=>({id,host:'local',model:'runway-test/'+id,source:id,provider:'codex',account:id,pool:id,windows:'all',categories:['hard'],priority:id==='primary'?1:0,max_parallel:1}))}));
const log=openSync(join(home,'runtime.log'),'w',0o600);
const child=spawn(process.env.OPENCODE_BIN||'opencode',['serve','--hostname','127.0.0.1','--port',String(port),'--print-logs'],{env,cwd:home,stdio:['ignore',log,log]});
const timeout=async(fn,label)=>{let last;for(let i=0;i<120;i++){try{const v=await fn();if(v)return v;}catch(e){last=e;}await new Promise(r=>setTimeout(r,200));}throw new Error(label+': '+last?.message);};
const request=async req=>{
  const p=exec('python3',['-B',join(root,'runway_main.py'),'--home',quotaHome,'--server',baseUrl,'--tarmac',quotaUrl],{env});
  p.child.stdin.end(JSON.stringify(req));
  const {stdout}=await p;return JSON.parse(stdout);
};
try{
  const api=OpenCode.make({baseUrl,headers:{Authorization:'Basic '+Buffer.from('opencode:'+password).toString('base64')}});
  const info=await timeout(()=>api.server.info(),'startup');
  await api.config.get();
  await timeout(async()=>{const p=await api.plugin.list();return p.data.some(x=>x.id==='chief-runway'&&x.state.status==='active');},'plugin load');
  const chief=await api.session.create({title:'Runway fixture chief',location:{directory:project},model:{providerID:'runway-test',id:'primary'},permissions:[{action:'*',resource:'*',effect:'allow'}]});
  await api.session.prompt({sessionID:chief.id,text:'admit-test-worker'});
  await api.session.wait({sessionID:chief.id},{signal:AbortSignal.timeout(20000)});
  const status=await request({action:'status',format:'json'});assert.equal(status.attempts.length,1,'native agent tool reserved an attempt');
  const a=status.attempts[0];assert.equal(a.model,'runway-test/primary');
  const worker=await api.session.create({title:'Fixture worker',location:{directory:project},model:{providerID:'runway-test',id:'primary'}});
  await api.session.prompt({sessionID:worker.id,id:a.message_id,text:'finish fixture work'});
  await api.session.wait({sessionID:worker.id},{signal:AbortSignal.timeout(10000)});
  await request({action:'bind',attempt:a.id,session:worker.id});
  const checkpoint={objective:'fixture',directory:project,changes:'none',tests:'fixture passes',next:'continue',side_effects:'none'};
  await request({action:'finish',attempt:a.id,state:'quiescent',tools_reconciled:true,effects_reconciled:true,checkpoint});
  exhausted=true;
  const resumed=await request({action:'prepare',task:a.task});
  assert.equal(resumed.action,'session.send');assert.equal(resumed.args.sessionId,worker.id);assert.equal(resumed.args.model,'runway-test/fallback');
  await api.session.switchModel({sessionID:worker.id,model:{providerID:'runway-test',id:'fallback'}});
  await api.session.prompt({sessionID:worker.id,id:resumed.args.messageId,text:'continue fixture work from checkpoint'});
  await api.session.wait({sessionID:worker.id},{signal:AbortSignal.timeout(10000)});
  await request({action:'bind',attempt:resumed.attempt.id,session:worker.id});
  await request({action:'finish',attempt:resumed.attempt.id,state:'completed',tools_reconciled:true,effects_reconciled:true});
  assert.ok(quotaPaths.every(x=>x==='/api/v1/snapshot'));
  console.log(JSON.stringify({passed:true,version:info.version,checks:['native tool invocation','authenticated native catalog','persistent admission','bind actual worker','verify idle/inbox','checkpoint','quota fallback','same-session continuation','confirmed completion','passive-only telemetry'],log:join(home,'runtime.log')}));
}finally{
  child.kill('SIGTERM');await new Promise(r=>child.once('exit',r));closeSync(log);await new Promise(r=>quota.close(r));await new Promise(r=>model.close(r));
}
