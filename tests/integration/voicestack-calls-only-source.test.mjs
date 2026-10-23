// FV-NO-MESSAGES exact owner landing. Offline schema/CLI help only, no calls/service.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {ordinaryArgv,sanitizeResult} from '../../services/voicestack/ordinary-call.mjs';

const root=process.env.CALL_TOOL_TEST_SOURCE;
const ref=process.env.CALL_TOOL_TEST_REF;
if (!root || !path.isAbsolute(root) || !/^[0-9a-f]{7,40}$/.test(ref??'')) throw Error('Explicit reviewed source root/hash required');
const git=args=>execFileSync('git',['-C',root,...args],{encoding:'utf8',timeout:5000,maxBuffer:262144});
const commit=git(['rev-parse','--verify',`${ref}^{commit}`]).trim();
const blobs=new Map(['reachout-policy.mjs','reachout.mjs','push-store.mjs','push-service.mjs','open-voice-control.mjs'].map(name=>
  [name,git(['show','--no-ext-diff','--no-textconv',`${commit}:bridge/${name}`])]));

test('landed ordinary sender accepts calls only, rejects notification and URL surfaces, with no execution',async t=>{
  const dir=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'fv-no-messages-')));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  for(const [name,source] of blobs)fs.writeFileSync(path.join(dir,name),source);
  const policy=await import(pathToFileURL(path.join(dir,'reachout-policy.mjs')));
  assert.deepEqual(policy.REACHOUT_REASONS,{'urgent-call':['decision','goal-risk']});
  const call={kind:'urgent-call',reason:'decision',session:'ses_fixture',id:'fixture-call',title:'Fixture choice',body:'Fixture choice'};
  assert.equal(policy.sendSchema(call).kind,'urgent-call');
  for(const bad of [{...call,kind:'need'},{...call,kind:'ready-to-try'}, {...call,url:'https://example.invalid/install'}])
    assert.throws(()=>policy.sendSchema(bad));
  const cli=await import(pathToFileURL(path.join(dir,'reachout.mjs')));
  // Never main/send: even dry-run should not be confused with production delivery proof.
  assert.throws(()=>cli.parseArgs(['dev-override','status']));
  assert.match(cli.USAGE,/messages and notifications go through Nod/);
  assert.match(cli.callAnswer({targets:[{delivery:'not-called',policyReason:'calls-disabled'}]}),/^not called:/);
  assert.match(blobs.get('reachout.mjs'),/timeoutMs = 15000/);
  assert.ok(!blobs.get('reachout.mjs').includes("from './dev-override.mjs'"));
  assert.ok(!blobs.get('push-service.mjs').includes('this.alert('));
  assert.ok(!blobs.get('open-voice-control.mjs').includes('this.push.alert('));
});

test('actual deployed CLI and backend preserve native-origin admission, call controls and duplicate fencing offline',async t=>{
  assert.equal(commit,'a181b63f188082e7c285d3fb119f22245b366b43','review this deployed contract explicitly');
  const dir=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'fv-ordinary-contract-')));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  for(const [name,source] of blobs)fs.writeFileSync(path.join(dir,name),source);
  const cli=await import(pathToFileURL(path.join(dir,'reachout.mjs')));
  const {PushService}=await import(pathToFileURL(path.join(dir,'push-service.mjs')));
  const {CONFIG}=await import(pathToFileURL(path.join(dir,'reachout-policy.mjs')));
  let apns=0,saves=0,warm=0,validations=0;let chief='ses_CHIEF';
  const store={data:{devices:{'d:fixture':{enrollment:{voipToken:'SYNTHETIC',environment:'sandbox',revision:1},
    settings:{callsEnabled:false,quietHoursEnabled:true,timeZone:'UTC'}}},records:{}},save(){saves++;}};
  const backend=new PushService({store,chief:()=>chief,activeDevices:()=>[{deviceID:'fixture'}],
    validateOrigin:async request=>{validations++;assert.equal(request.messageID,'msg_A');},
    apns:async()=>{apns++;return {status:200};},speechKeepalive:async()=>{throw Error('no speech/network');}});
  const body={operation_id:'00000000-0000-4000-8000-000000000001',reason:'decision',title:'Fixture',body:'Choose next step'};
  const args=ordinaryArgv('/synthetic',body,{sessionID:'ses_CHIEF',messageID:'msg_A'}).slice(1);
  assert.deepEqual(cli.parseArgs(args).request,{kind:'urgent-call',reason:'decision',session:'ses_CHIEF',id:body.operation_id,
    title:body.title,body:body.body,messageID:'msg_A'});
  const dependencies={ensureSpeech:async()=>{warm++;return {ready:true};},answerWait:{timeoutMs:0},
    sender:request=>request.command==='send'?backend.send(request.request):backend.status(request.id)};
  const first=await cli.main(args,dependencies);await backend.drain();
  assert.equal(first.id,body.operation_id);assert.equal(apns,1);assert(saves>0);assert.equal(validations,1);
  assert.equal(sanitizeResult(body.operation_id,0,JSON.stringify(first)).state,'recorded');
  await cli.main(args,dependencies);await backend.drain();assert.equal(apns,1); // durable same-ID coalescing
  await assert.rejects(cli.main(args.map(x=>x==='Fixture'?'Changed':x),dependencies),/different intent/);
  chief='ses_NEW';await assert.rejects(cli.main(args,dependencies),/current chief/);assert.equal(apns,1);
  chief='ses_CHIEF';backend.validateOrigin=async()=>{throw Error('native origin denied');};
  await assert.rejects(cli.main(args,dependencies),/native origin denied/);assert.equal(apns,1);
  backend.validateOrigin=async()=>{};
  const second=args.map(x=>x===body.operation_id?'00000000-0000-4000-8000-000000000002':x);
  const held=await cli.main(second,dependencies);assert.equal(held.targets[0].policyReason,'call-outstanding');assert.equal(apns,1);
  backend.config={...CONFIG,callsEnabled:false};
  const disabled=await cli.main(args.map(x=>x===body.operation_id?'00000000-0000-4000-8000-000000000003':x),dependencies);
  assert.equal(disabled.targets[0].policyReason,'calls-disabled');assert.equal(apns,1);
  let sends=0;const notReady=await cli.main(args,{ensureSpeech:async()=>({ready:false}),sender:async()=>{sends++;}});
  assert.equal(notReady.reason,'speech_not_ready');assert.equal(sends,0);
  // Ordinary quiet-hours gate is receiver-side; backend deliberately ignores cached settings.
  assert.match(cli.callAnswer({targets:[{message:'in quiet hours until 09:00'}]}),/^declined: in quiet hours/);
  assert.match(cli.awaitCallAnswer.toString(),/timeoutMs = 15000/);
  assert.match(cli.ensureCallSpeech.toString(),/budgetMs = 150000/);
  assert.match(cli.USAGE,/no daily\/spacing cap/);assert(warm>0);
});
