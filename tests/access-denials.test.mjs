import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { observeDenial, redactPath, reviewRecord } from '../access/denials.mjs';

const model=JSON.parse(await readFile(new URL('../access/model.json',import.meta.url),'utf8'));
const compilation={modelRevision:model.revision,binding:{id:'fixture-writer',role:'writer',home:'/fixture/home',location:'/fixture/project'},
  ruleManifest:[{id:'base.default-deny',action:'*',resource:'*',effect:'deny',reason:'default-deny'},
    {id:'secret.chief.read',action:'read',resource:'/fixture/home/.chief-of-staff/secrets/*',effect:'deny',reason:'secret-owner-only'}]};
const context={sessionID:'ses_fixture',agentID:'writer',compilation,observedAt:'2026-10-22T16:00:00Z',
  publicPaths:['/fixture/project/src/main.py','/fixture/home/.chief-of-staff/research/result.md'],
  pathRoots:[{id:'project',path:'/fixture/project'},{id:'research',path:'/fixture/home/.chief-of-staff/research'},
    {id:'secrets',path:'/fixture/home/.chief-of-staff/secrets',protected:true}]};
const event=(cause,extra={})=>({status:'error',tool:'read',sessionID:'ses_fixture',agent:'writer',messageID:'msg_fixture',id:'call_fixture',
  input:{path:'/fixture/home/.chief-of-staff/research/result.md'},error:{message:'DO-NOT-LOG',error:cause},...extra});

test('structured native deny maps only exact exposed last-winning rule and redacts secret tail',()=>{
  const e=event({_tag:'Permission.BlockedError',permission:'read',resources:['/fixture/home/.chief-of-staff/secrets/FAKE_TOKEN_SENTINEL'],
    rules:[{action:'*',resource:'*',effect:'allow'},compilation.ruleManifest[1]]});
  const r=observeDenial(e,context);
  assert.equal(r.denyingRule.id,'secret.chief.read');assert.equal(r.action,'read');
  assert.equal(r.path.value,'@secrets/<redacted>');assert.equal(r.ruleEvidence,'native-deny-mapped-to-generated-rule');
  assert.ok(!JSON.stringify(r).includes('FAKE_TOKEN_SENTINEL'));assert.ok(!JSON.stringify(r).includes('DO-NOT-LOG'));
});

test('persisted permission.rejected cannot fabricate rule OR action from tool/message',()=>{
  const r=observeDenial(event({type:'permission.rejected',message:'Permission denied: read SECRET_VALUE'}),context);
  assert.equal(r.denyingRule,null);assert.equal(r.action,null);assert.equal(r.path.value,'@research/result.md');
  assert.equal(r.ruleEvidence,'serialized-error-rule-not-exposed');assert.ok(!JSON.stringify(r).includes('SECRET_VALUE'));
});

test('policy hook deny with only allow rules remains unknown, not model-replayed as native proof',()=>{
  const r=observeDenial(event({_tag:'Permission.BlockedError',permission:'read',resources:['/fixture/project/a.md'],
    rules:[{action:'read',resource:'*',effect:'allow'}]}),context);
  assert.equal(r.denyingRule,null);assert.equal(r.ruleEvidence,'native-rules-exposed-without-a-denying-rule');
});

test('identical native triples with multiple generated IDs cannot invent rule provenance',()=>{
  const ctx={...context,compilation:{...compilation,ruleManifest:[...compilation.ruleManifest,
    {...compilation.ruleManifest[1],id:'different-owner-reason'}]}};
  const r=observeDenial(event({_tag:'Permission.BlockedError',permission:'read',resources:['/fixture/home/.chief-of-staff/secrets/no'],
    rules:[compilation.ruleManifest[1]]}),ctx);
  assert.equal(r.denyingRule,null);assert.equal(r.ruleEvidence,'native-deny-present-generated-id-ambiguous');
});

test('shell command/env/unknown denying pattern are never serialized',()=>{
  const r=observeDenial(event({_tag:'Permission.BlockedError',permission:'shell',resources:['curl -H Authorization:FAKE_CREDENTIAL'],
    rules:[{action:'shell',resource:'curl -H Authorization:FAKE_CREDENTIAL',effect:'deny'}]},
    {tool:'shell',input:{command:'curl FAKE_CREDENTIAL',env:{TOKEN:'FAKE_CREDENTIAL'},workdir:'/fixture/project'}}),context);
  assert.equal(r.action,'shell');assert.equal(r.denyingRule,null);
  assert.equal(r.ruleEvidence,'native-deny-present-but-unmapped-redacted');assert.equal(r.path.value,'@project');
  assert.ok(!JSON.stringify(r).includes('FAKE_CREDENTIAL'));assert.ok(!JSON.stringify(r).includes('curl'));
});

test('wrong session/agent binding never supplies another role, path or generated-rule attribution',()=>{
  const r=observeDenial(event({_tag:'Permission.BlockedError',permission:'read',resources:['/fixture/home/.chief-of-staff/secrets/x'],
    rules:[compilation.ruleManifest[1]]},{sessionID:'ses_other'}),context);
  assert.equal(r.role,'unbound');assert.equal(r.path.value,null);assert.equal(r.denyingRule,null);
});

test('unknown high-entropy/private paths redact; normalization resolves before bound-root selection',()=>{
  assert.equal(redactPath('/elsewhere/FAKE_SECRET',context).value,null);
  assert.equal(redactPath('../project/src/main.py',context).value,'@project/src/main.py');
  assert.equal(redactPath('/fixture/project/'+ 'a'.repeat(40),context).status,'redacted');
  assert.equal(redactPath('/fixture/project/password=FAKE',context).value,'@project/<redacted>');
  assert.equal(redactPath('/fixture/project/short-fake-credential',context).value,'@project/<redacted>');
});

test('multiple native resources attribute a real deny; malformed or oversized lists stay unknown',()=>{
  const cause={_tag:'Permission.BlockedError',permission:'read',resources:['/fixture/project/allowed.md','/fixture/home/.chief-of-staff/secrets/no'],
    rules:[{action:'read',resource:'*',effect:'allow'},compilation.ruleManifest[1]]};
  const actual=observeDenial(event(cause),context);
  assert.equal(actual.denyingRule.id,'secret.chief.read');assert.equal(actual.path.value,'@secrets/<redacted>');
  for (const rules of ([[{}]],Array(513).fill(compilation.ruleManifest[1]))) {
    assert.equal(observeDenial(event({...cause,rules}),context).denyingRule,null);
  }
});

test('ordinary errors/non-errors are not permission denials and source messages are not parsed',()=>{
  assert.equal(observeDenial(event({message:'Permission denied: read'}),context),null);
  assert.equal(observeDenial({...event({type:'permission.rejected'}),status:'completed'},context),null);
});

test('review records rationale/regression as DATA and cannot grant/retry',()=>{
  const r=observeDenial(event({type:'permission.rejected'}),context);
  assert.throws(()=>reviewRecord(r,{disposition:'correct-denial'},model));
  assert.equal(reviewRecord(r,{disposition:'correct-denial',reason:'secret-owner-only'},model).effects,'none');
  assert.throws(()=>reviewRecord(r,{disposition:'model-defect'},model));
  assert.equal(reviewRecord(r,{disposition:'model-defect',matrixCase:'secret-root'},model).matrixCase,'secret-root');
  assert.throws(()=>reviewRecord(r,{disposition:'correct-denial',reason:'default-deny',allow:true},model));
});

test('source-only end to end: central compiler -> custom body-preserving emission -> native-shaped deny -> redacted record',()=>{
  const root=fileURLToPath(new URL('../',import.meta.url));
  const code=`import sys,json;sys.path.insert(0,'scripts');from access_policy import *
m=json.loads(MODEL.read_text());b=fixture_binding(m,'writer')
t='---\\n'+json.dumps({'description':'Custom','model':'unchanged','permissions':[{'action':'*','resource':'*','effect':'deny'}]})+'\\n---\\nExact custom body\\n'
c,emitted=compile_for_agent(m,b,t,managed_baseline=[{'action':'*','resource':'*','effect':'deny'}])
d=evaluate(c,'read',b['home']+'/.chief-of-staff/secrets/harmless-sentinel')
print(json.dumps({'compilation':c,'decision':d,'bodyPreserved':emitted.endswith('Exact custom body\\n')}))`;
  const run=spawnSync('python3',['-B','-c',code],{cwd:root,encoding:'utf8',timeout:10000});
  assert.equal(run.status,0,run.stderr);
  const result=JSON.parse(run.stdout),c=result.compilation,d=result.decision;
  assert.equal(result.bodyPreserved,true);assert.equal(c.installable,false);assert.equal(c.run.selected,null);
  const ctx={...context,compilation:c};
  const nativeShaped=event({_tag:'Permission.BlockedError',permission:d.action,resources:[d.resource],
    rules:c.nativeRules.filter(r=>r.action==='*'||r.action===d.action)});
  const record=observeDenial(nativeShaped,ctx);
  assert.equal(record.denyingRule.id,d.id);assert.equal(record.modelRevision,model.revision);
  assert.equal(record.path.value,'@secrets');
  assert.equal(record.effects,'observation-only-no-retry-no-grant');
});
