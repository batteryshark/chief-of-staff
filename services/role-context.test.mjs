import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {filterTools, matches, setup} from './role-context.mjs';

test('normal installer uses discovered native JavaScript plugin entry', () => {
  const installer = readFileSync(new URL('../install.sh', import.meta.url), 'utf8');
  assert.ok(installer.includes('plugins/chief-role-context.js|'));
  assert.ok(!installer.includes('plugins/chief-role-context.mjs|'));
  assert.ok(!installer.includes('context_plugin_candidate'));
});

test('request diet preserves execution, memory, plans and dispatch; workers unchanged', () => {
  for (const agent of ['chief-of-staff', 'lead', 'writer']) {
    const event = {agent, tools: Object.fromEntries(['read','patch','execute','opencode_session_move',
      'openchamber','openchamber_knowledge','runway','a2a_send','unrelated_tool'].map(id => [id, {}]))};
    filterTools(event);
    assert.equal(Object.keys(event.tools).length, 8);
    assert.ok(!event.tools.unrelated_tool);
  }
  const event = {agent: 'build', tools: {unrelated_tool: {}}};
  filterTools(event);
  assert.ok(event.tools.unrelated_tool);
});
test('dispatcher is resolve-only and patterns are anchored/literal', () => {
  const event = {agent: 'heartbeat-pilot-dispatcher', tools: {execute: {}, heartbeat_resolve: {}, read: {}}};
  filterTools(event);
  assert.deepEqual(Object.keys(event.tools), ['heartbeat_resolve']);
  assert.ok(matches('reset-dispatch', ['reset-*']));
  assert.ok(!matches('xreset-dispatch', ['reset-*']));
  assert.ok(!matches('axb', ['a.b']));
});
test('setup only hooks direct schemas; no early registry reads or permission mutations', async () => {
  let disposed = 0;
  let hook;
  const cleanup = await setup({
    session: {hook: async (name, callback) => {
      assert.equal(name, 'context'); hook = callback;
      return {dispose: async () => disposed++};
    }},
  });
  const lead = {agent:'lead', tools:{execute:{}, openchamber_schedule:{}}};
  hook(lead); assert.deepEqual(Object.keys(lead.tools), ['execute']);
  const writer = {agent:'writer', tools:{actual_writer_dependency:{}}};
  hook(writer); assert.ok(writer.tools.actual_writer_dependency);
  await cleanup(); assert.equal(disposed, 1);
});
test('reviewed exact writer dependencies override default without aliases', async () => {
  let hook;
  const cleanup = await setup({options:{roleTools:{writer:['actual_writer_dependency','execute']}},
    session: {hook: async (_, cb) => {hook=cb; return {dispose: async () => {}};}},
  });
  const writer = {agent:'writer', tools:{actual_writer_dependency:{},execute:{},unrelated:{}}};
  hook(writer); assert.deepEqual(Object.keys(writer.tools), ['actual_writer_dependency','execute']);
  await cleanup();
});
