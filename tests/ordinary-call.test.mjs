import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
import plugin,{createOrdinaryCallPlugin,inputSchema,ordinaryArgv,sanitizeResult,operationBudgetMs} from '../services/voicestack/ordinary-call.mjs';

const input=()=>({operation_id:randomUUID(),reason:'decision',title:'Choose next step',body:'A decision is needed.'});
const context=()=>({sessionID:'ses_CHIEF',agent:'chief',messageID:'msg_A',id:'call_A',signal:new AbortController().signal});
const hash=x=>createHash('sha256').update(x).digest('hex');
async function fixture(t,script,permission=async()=>{}) {
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'ordinary-call-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  fs.mkdirSync(path.join(root,'bridge'));fs.mkdirSync(path.join(root,'attempts'),{mode:0o700});
  fs.writeFileSync(path.join(root,'chief.json'),JSON.stringify({session:'ses_CHIEF',directory:root}));
  fs.writeFileSync(path.join(root,'bridge/reachout.mjs'),script);
  const binding={nodePath:process.execPath,codeRoot:root,chiefPointerFile:path.join(root,'chief.json'),directory:root,
    agentID:'chief',attemptDirectory:path.join(root,'attempts'),cliSha256:hash(script)};
  let def,lookups=0;
  const ctx={session:{get:async()=>{lookups++;return {data:{id:'ses_CHIEF',agent:'chief',location:{directory:root}}};}},
    permission:{assert:permission},tool:{transform:async fn=>{fn({add:d=>{def=d;}});return{dispose:async()=>{}};}}};
  await createOrdinaryCallPlugin(binding).setup(ctx);
  return {root,binding,ctx,def,lookups:()=>lookups,run:async(body=input(),c=context())=>JSON.parse((await def.execute(body,c)).content)};
}
const success=`import fs from 'node:fs';const a=process.argv.slice(2);fs.appendFileSync('calls','1');
fs.writeFileSync('argv.json',JSON.stringify({argv:a,env:Object.keys(process.env)}));
const id=a[a.indexOf('--id')+1];console.error('ringing');console.log(JSON.stringify({id,disposition:'call-intent',
 targets:[{delivery:'call-intent',policyReason:'urgent-eligible'}],answer:'ringing'}));`;

test('default inert; separate closed ordinary schema and enum, no managed capability',async()=>{
  await plugin.setup(new Proxy({},{get(){throw Error('unbound startup');}}));
  assert.deepEqual(inputSchema.properties.reason.enum,['decision','goal-risk']);
  assert.equal(inputSchema.additionalProperties,false);assert.equal(operationBudgetMs,200000);
  assert.throws(()=>createOrdinaryCallPlugin({nodePath:'node'}),/binding/);
});

test('real child receives fixed argv, no shell/env; stderr receipt is allowed, attempt is fenced',async t=>{
  const f=await fixture(t,success),body=input();body.body='Literal $(touch NEVER) ; --kind message';
  const value=await f.run(body);assert.equal(value.state,'recorded');assert.equal(value.phoneReceipt,'ringing');
  assert.equal(value.targets[0].delivery,'call-intent');assert.equal(value.media,'not-proven');
  const seen=JSON.parse(fs.readFileSync(path.join(f.root,'argv.json')));
  assert.deepEqual(seen.argv,ordinaryArgv(f.root,body,context()).slice(1));
  assert.deepEqual(seen.env.filter(x=>x!=='__CF_USER_TEXT_ENCODING'),[]);
  assert.equal((await f.run(body)).reason,'already-attempted-inspect-status');
  assert.equal(fs.readFileSync(path.join(f.root,'calls'),'utf8'),'1');assert(!fs.existsSync(path.join(f.root,'NEVER')));
  const marker=fs.readFileSync(path.join(f.root,'attempts',body.operation_id+'.json'),'utf8');
  assert(!marker.includes(body.body));assert(!marker.includes(body.title));
  let def;await createOrdinaryCallPlugin(f.binding).setup({...f.ctx,tool:{transform:async fn=>fn({add:d=>{def=d;}})}});
  assert.equal(JSON.parse((await def.execute(body,context())).content).reason,'already-attempted-inspect-status');
});

test('caller, schema, permission and changed-source refusals precede all CLI effects',async t=>{
  let permissions=0;const f=await fixture(t,success,async p=>{permissions++;assert.equal(p.action,'chief_urgent_call');assert.deepEqual(p.resources,['ordinary-urgent-call']);});
  for(const extra of [{reason:'voice-quicker'},{kind:'urgent-call'},{session:'ses_OTHER'},{url:'https://invalid.example'},
    {title:'Milestone'},{body:'x\ny'},{operation_id:'../outside'}])assert.equal((await f.run({...input(),...extra})).state,'refused');
  assert.equal(permissions,0);
  for(const c of [{...context(),agent:'lead'},{...context(),sessionID:'ses_OTHER'}])assert.equal((await f.run(input(),c)).state,'refused');
  f.ctx.session.get=async()=>({id:'ses_CHIEF',agent:'chief',location:{directory:'/other'}});
  assert.equal((await f.run()).state,'refused');
  f.ctx.session.get=async()=>({id:'ses_CHIEF',agent:'chief',location:{directory:f.root},time:{archived:1}});
  assert.equal((await f.run()).state,'refused');
  f.ctx.session.get=async()=>({id:'ses_CHIEF',agent:'chief',location:{directory:f.root}});
  fs.appendFileSync(path.join(f.root,'bridge/reachout.mjs'),'\n// drift');
  assert.equal((await f.run()).reason,'reviewed-cli-changed');
  assert(!fs.existsSync(path.join(f.root,'calls')));assert.deepEqual(fs.readdirSync(path.join(f.root,'attempts')),[]);
  const denied=await fixture(t,success,async()=>{throw Error('native permission.rejected');});
  await assert.rejects(denied.run(),/permission.rejected/);assert.equal(denied.lookups(),0);
});

test('fresh pointer changes, cancellation and lookup failure cannot admit an attempt',async t=>{
  const f=await fixture(t,success);
  f.ctx.session.get=async()=>{fs.writeFileSync(f.binding.chiefPointerFile,JSON.stringify({session:'ses_NEW',directory:f.root}));return {id:'ses_CHIEF',agent:'chief',location:{directory:f.root}};};
  assert.equal((await f.run()).state,'refused');
  const c=context();c.signal=AbortSignal.abort();assert.equal((await f.run(input(),c)).state,'refused');
  assert.deepEqual(fs.readdirSync(path.join(f.root,'attempts')),[]);
});

test('uncertain, malformed, oversized and cancelled child outcomes are redacted and never replayed',async t=>{
  for(const code of ["console.log('PRIVATE_SECRET');process.exitCode=1;","console.log('x'.repeat(70000));", "console.error('SECRET');setInterval(()=>{},1000);"]){
    const f=await fixture(t,`import fs from 'node:fs';fs.appendFileSync('calls','1');${code}`),body=input();
    const value=await f.run(body,{...context(),signal:AbortSignal.timeout(250)});
    assert.equal(value.state,'unknown');assert(!JSON.stringify(value).includes('SECRET'));
    assert.equal((await f.run(body)).reason,'already-attempted-inspect-status');assert.equal(fs.readFileSync(path.join(f.root,'calls'),'utf8'),'1');
  }
});

test('only known result fields and first-receipt vocabulary survive redaction',()=>{
  const id=randomUUID();const raw={id,targets:[{delivery:'apns-accepted',policyReason:'urgent-eligible',receipt:'answered',token:'SECRET'}],
    answer:'declined: in quiet hours until 09:00',request:{body:'SECRET'}};
  const value=sanitizeResult(id,0,JSON.stringify(raw));assert.equal(value.quietUntilLocal,'09:00');
  assert.equal(value.phoneReceipt,'declined');assert(!JSON.stringify(value).includes('SECRET'));
  assert.equal(sanitizeResult(id,1,JSON.stringify({id,outcome:'refused',reason:'speech_not_ready',detail:'SECRET'})).state,'not-sent');
  for(const r of [{...raw,id:'wrong'},{id,error:'SECRET',status:503}])assert.equal(sanitizeResult(id,1,JSON.stringify(r)).state,'unknown');
  assert.equal(sanitizeResult(id,0,JSON.stringify({...raw,answer:'SECRET'})).phoneReceipt,'unknown');
});
