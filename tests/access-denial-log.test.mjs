import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, chmod, readFile, stat, symlink, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { denialLog } from '../access/denial-log.mjs';
import { observeDenial } from '../access/denials.mjs';

test('private JSONL deduplicates concurrent and reopened observations without logging raw error/input',async()=>{
  const dir=await mkdtemp(path.join(await realpath(tmpdir()),'access-log-test-'));
  await chmod(dir,0o700);
  const file=dir+'/denials.jsonl';
  const record=observeDenial({status:'error',tool:'shell',sessionID:'ses_test',agent:'fixture',
    messageID:'msg_test',id:'call_test',input:{command:'DO_NOT_LOG_COMMAND',env:{TOKEN:'DO_NOT_LOG_ENV'}},
    error:{type:'permission.rejected',message:'DO_NOT_LOG_SECRET'}},{sessionID:'ses_test',agentID:'fixture',
    compilation:{modelRevision:'test',binding:{id:'test',role:'worker',location:dir,home:'/fixture/home'},ruleManifest:[]}});
  const sink=await denialLog(file);
  const results=await Promise.all([sink.append(record),sink.append(record)]);
  assert.deepEqual(results.map(r=>r.status),['appended','duplicate']);await sink.close();
  const reopened=await denialLog(file);assert.equal((await reopened.append(record)).status,'duplicate');await reopened.close();
  const text=await readFile(file,'utf8');assert.equal(text.trim().split('\n').length,1);
  assert.ok(!text.includes('DO_NOT_LOG'));assert.equal((await stat(file)).mode&0o777,0o600);
  assert.equal(JSON.parse(text).action,null);assert.equal(JSON.parse(text).denyingRule,null);
});

test('log refuses symlink leaves and nonprivate directories, not broad chmod or retry',async()=>{
  const dir=await mkdtemp(path.join(await realpath(tmpdir()),'access-log-test-'));await chmod(dir,0o700);
  await symlink(dir+'/elsewhere',dir+'/denials.jsonl');await assert.rejects(denialLog(dir+'/denials.jsonl'));
  await chmod(dir,0o755);await assert.rejects(denialLog(dir+'/other.jsonl'));
});

test('actual native loss of action in serialized fallback does not duplicate a correlated call',async()=>{
  const dir=await mkdtemp(path.join(await realpath(tmpdir()),'access-log-test-'));await chmod(dir,0o700);
  const context={sessionID:'ses_test',agentID:'fixture',compilation:{modelRevision:'test',
    binding:{id:'test',role:'worker',location:dir,home:'/fixture/home'},ruleManifest:[]}};
  const source={status:'error',tool:'read',sessionID:'ses_test',agent:'fixture',messageID:'msg_test',id:'call_test'};
  const raw=observeDenial({...source,error:{error:{_tag:'Permission.BlockedError',permission:'read',
    resources:['configured-deny.txt'],rules:[{action:'read',resource:'configured-deny.txt',effect:'deny'}]}}},context);
  const serialized=observeDenial({...source,error:{type:'permission.rejected'}},context);
  assert.notEqual(raw.id,serialized.id);assert.equal(serialized.action,null);assert.equal(serialized.denyingRule,null);
  const sink=await denialLog(dir+'/denials.jsonl');
  assert.equal((await sink.append(raw)).status,'appended');assert.equal((await sink.append(serialized)).status,'duplicate');
  await sink.close();assert.equal((await readFile(dir+'/denials.jsonl','utf8')).trim().split('\n').length,1);
});
