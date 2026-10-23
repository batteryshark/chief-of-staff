// Native wrapper executor with actual pinned Python helper; TEMP HOME/rosters only.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import plugin,{createMilestonePlugin,helperFiles,inputSchema} from '../../services/docket/milestone.mjs';

const source=process.env.DOCKET_MILESTONE_TEST_SOURCE;
if(!source||!path.isAbsolute(source))throw Error('Explicit DOCKET_MILESTONE_TEST_SOURCE required');
const pin='91a6b58c2f6d98add8eeb68cdd465667d3ccdf3f';
const git=args=>execFileSync('git',['-C',source,...args],{encoding:'utf8',timeout:5000,maxBuffer:262144});
const names=git(['ls-tree','-r','--name-only',pin,'docket']).trim().split('\n').filter(p=>p.endsWith('.py'));
const files=Object.fromEntries(names.map(p=>[p,git(['show',pin+':'+p])]));
const sha=b=>createHash('sha256').update(b).digest('hex');
const c=()=>({sessionID:'ses_own',agent:'lead',messageID:'msg_A',id:'call_A',signal:new AbortController().signal});
const input={milestone_at:'2026-10-21T12:00:00Z',milestone_ref:'Synthetic accepted result'};
async function fixture(t){
  const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'milestone-wrapper-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const code=path.join(root,'source'),home=path.join(root,'home'),roster=path.join(home,'.docket/lead-checkins.jsonl');
  fs.mkdirSync(code);for(const [p,text]of Object.entries(files)){fs.mkdirSync(path.dirname(path.join(code,p)),{recursive:true});fs.writeFileSync(path.join(code,p),text);}
  fs.mkdirSync(path.dirname(roster),{recursive:true,mode:0o700});fs.chmodSync(path.dirname(roster),0o700);
  const own={session:'ses_own',directory:'/fixture/own',state:'hold',extra:{preserved:true}};
  const foreign=' {"session":"ses_foreign", "directory":"/fixture/foreign", "state":"done"}\n';
  const raw=JSON.stringify(own)+'\n\n'+foreign;fs.writeFileSync(roster,raw,{mode:0o600});
  const binding={pythonPath:'/usr/bin/python3',sourceRoot:code,home,callers:[{sessionID:'ses_own',agentID:'lead',directory:'/fixture/own'}],
    sourceHashes:Object.fromEntries(helperFiles.map(p=>[p,sha(files[p])]))};
  let def;let permissions=0;
  const ctx={permission:{assert:async p=>{permissions++;assert.equal(p.action,'docket_milestone');assert.deepEqual(p.resources,['own']);}},
    session:{get:async()=>({data:{id:'ses_own',agent:'lead',location:{directory:'/fixture/own'}}})},
    tool:{transform:async fn=>{fn({add:d=>def=d});return{dispose:async()=>{}};}}};
  await createMilestonePlugin(binding).setup(ctx);
  return {root,code,home,roster,raw,own,foreign,binding,ctx,permissions:()=>permissions,run:async(v=input,caller=c())=>JSON.parse((await def.execute(v,caller)).content)};
}

test('default is inert and input has only milestone pair',async()=>{
  await plugin.setup(new Proxy({},{get(){throw Error('no binding');}}));
  assert.equal(inputSchema.additionalProperties,false);assert.deepEqual(Object.keys(inputSchema.properties),['milestone_at','milestone_ref']);
});
test('actual pinned helper updates own pair, preserves held/foreign data and mode; duplicate unchanged',async t=>{
  const f=await fixture(t);const old={...process.env};
  process.env.DOCKET_HOME='/must-not-use';process.env.PYTHONPATH='/must-not-use';process.env.DOCKET_CALLER_SESSION='ses_foreign';
  try {assert.equal((await f.run()).status,'recorded');} finally {process.env=old;}
  const after=fs.readFileSync(f.roster,'utf8');assert(after.endsWith('\n\n'+f.foreign));
  const row=JSON.parse(after.split('\n')[0]);assert.equal(row.state,'hold');assert.deepEqual(row.extra,f.own.extra);
  assert.equal(row.milestone_ref,input.milestone_ref);assert.equal(row.milestone_at,'2026-10-21T12:00:00+00:00');
  assert.equal(fs.statSync(f.roster).mode&0o777,0o600);assert.equal(fs.statSync(path.dirname(f.roster)).mode&0o777,0o700);
  assert.equal((await f.run()).status,'unchanged');assert.equal(f.permissions(),2);
});
test('foreign caller, model identity/path/env selectors, wrong native Location and permission denial make no edit',async t=>{
  const f=await fixture(t);
  for(const field of ['owner','session','directory','path','env','argv','state','HOME'])assert.equal((await f.run({...input,[field]:'other'})).status,'refused');
  assert.equal((await f.run(input,{...c(),sessionID:'ses_foreign'})).status,'refused');assert.equal(f.permissions(),0);
  f.ctx.session.get=async()=>({id:'ses_own',agent:'lead',location:{directory:'/fixture/foreign'}});
  assert.equal((await f.run()).status,'refused');
  f.ctx.permission.assert=async()=>{throw Error('permission.rejected');};await assert.rejects(f.run(),/permission.rejected/);
  assert.equal(fs.readFileSync(f.roster,'utf8'),f.raw);
});
test('absent enrollment, helper refusal, privacy failure and source drift cannot publish or auto repair',async t=>{
  const f=await fixture(t);fs.writeFileSync(f.roster,f.foreign);
  // Nonzero helper result can also occur after fsync failure; wrapper conservatively reports unknown.
  assert.equal((await f.run()).status,'unknown');assert.equal(fs.readFileSync(f.roster,'utf8'),f.foreign);
  fs.writeFileSync(f.roster,f.raw);fs.chmodSync(f.roster,0o644);
  assert.equal((await f.run()).status,'unknown');assert.equal(fs.statSync(f.roster).mode&0o777,0o644);
  fs.chmodSync(f.roster,0o600);fs.appendFileSync(path.join(f.code,'docket/milestone.py'),'\n# changed');
  assert.equal((await f.run()).status,'refused');assert.equal(fs.readFileSync(f.roster,'utf8'),f.raw);
});
test('cancelled native invocation does not start helper',async t=>{
  const f=await fixture(t);assert.equal((await f.run(input,{...c(),signal:AbortSignal.abort()})).status,'refused');
  assert.equal(fs.readFileSync(f.roster,'utf8'),f.raw);assert(!fs.existsSync(path.join(f.home,'.docket/.lead-checkins.lock')));
});
test('fixed Python flags and sanitized environment; unrecognized child output never leaks',async t=>{
  const f=await fixture(t);let def;
  const script=`import json,os,sys\nfrom pathlib import Path\nPath.home().joinpath('proof.json').write_text(json.dumps({'env':dict(os.environ),'argv':sys.argv,'ignore_environment':sys.flags.ignore_environment,'no_user_site':sys.flags.no_user_site,'dont_write_bytecode':sys.flags.dont_write_bytecode}))\nprint('PRIVATE_SENTINEL')\n`;
  fs.writeFileSync(path.join(f.code,'docket/milestone.py'),script);f.binding.sourceHashes['docket/milestone.py']=sha(script);
  await createMilestonePlugin(f.binding).setup({...f.ctx,tool:{transform:async fn=>fn({add:d=>def=d})}});
  const result=JSON.parse((await def.execute(input,c())).content);assert.equal(result.status,'unknown');
  assert(!JSON.stringify(result).includes('PRIVATE_SENTINEL'));
  const proof=JSON.parse(fs.readFileSync(path.join(f.home,'proof.json')));
  assert.equal(proof.env.HOME,f.home);assert.equal(proof.env.DOCKET_CALLER_SESSION,'ses_own');
  assert.equal(proof.env.DOCKET_CALLER_DIRECTORY,'/fixture/own');
  assert(!('DOCKET_HOME' in proof.env));assert(!('PYTHONPATH' in proof.env));assert(!('PATH' in proof.env));
  assert.equal(proof.ignore_environment,1);assert.equal(proof.no_user_site,1);assert.equal(proof.dont_write_bytecode,1);
  assert.equal(proof.argv.length,1);assert.equal(fs.readFileSync(f.roster,'utf8'),f.raw);
});
