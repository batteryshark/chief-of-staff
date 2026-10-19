import test from 'node:test';
import assert from 'node:assert/strict';
import {serverFromArgv} from '../routing/plugin.js';
import Plugin from '../routing/plugin.js';

test('server discovery uses a valid local port only',()=>{
  assert.equal(serverFromArgv(['opencode','serve','--port','9988']),'http://127.0.0.1:9988');
  assert.equal(serverFromArgv(['opencode','--port=9988']),'http://127.0.0.1:9988');
  for(const port of ['-1','0','65536','x','8080/path']) assert.equal(serverFromArgv(['--port',port]),undefined);
});
test('plugin registers one tool without changing models or dispatching',async()=>{
  const added=[];
  await Plugin.setup({tool:{transform:async f=>f({add:t=>added.push(t)})}});
  assert.equal(added.length,1);assert.equal(added[0].name,'runway');
  assert.equal(added[0].input.safeParse({request:'{}'}).success,true);
});
