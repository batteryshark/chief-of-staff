import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import plugin, {createNativeManagedCallPlugin} from '../services/voicestack/opencode.js';

test('owner-code composition registers only call tool without startup metadata or credential reads', async () => {
  const noRead=() => {throw Error('startup read forbidden');};
  const bindings={nodePath:process.execPath,codeRoot:path.resolve('.'),
    ownerResolvers:{resolveCaller:noRead,resolveGrant:noRead}};
  const definitions=[];
  const ctx={get session(){return noRead();},get location(){return noRead();},
    tool:{transform:async cb => cb({add:d => definitions.push(d)})}};
  await plugin.setup(ctx);
  assert.equal(definitions.length,0);
  await createNativeManagedCallPlugin(bindings).setup(ctx);
  assert.equal(definitions.length,0); // managed-call-v1 was never deployed
  await createNativeManagedCallPlugin({...bindings,fixtureOnly:true}).setup(ctx);
  assert.deepEqual(definitions.map(d => d.name),['chief_call']);
  assert.deepEqual(Object.keys(definitions[0].input.properties),['operation_id','reason','summary']);
  assert.equal(definitions[0].options.codemode,false);
  assert.throws(() => createNativeManagedCallPlugin({...bindings,ownerResolvers:{}}),/Invalid managed call binding/);
  assert.throws(() => createNativeManagedCallPlugin({...bindings,codeRoot:'relative'}),/Invalid managed call binding/);
});
