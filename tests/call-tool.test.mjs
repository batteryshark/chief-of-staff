import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import plugin, {createManagedCallPlugin,inputSchema} from '../services/voicestack/opencode.js';

const caller = {version:1,role:'chief',session_id:'ses_fixtureExisting',agent_id:'build',project_id:'fixture-project',directory:'/synthetic/project'};
const runtime = () => ({sessionID:caller.session_id,agent:'build',messageID:'msg_fixture',id:'call_fixture',signal:new AbortController().signal});
const body = () => ({operation_id:randomUUID(),reason:'decision',summary:'Fixture choice'});
async function tool(binding, permission = async () => {}) {
  let definition;
  await createManagedCallPlugin({...binding,fixtureOnly:true}).setup({permission:{assert:permission},tool:{transform:async cb => cb({add:d => {definition=d;}})}});
  return definition;
}
const run = async (t,b=body(),c=runtime()) => JSON.parse((await t.execute(b,c)).content);

test('default unbound plugin does nothing; closed schema', async () => {
  await plugin.setup(new Proxy({}, {get(){throw Error('startup access');}}));
  assert.equal(inputSchema.additionalProperties,false);
  assert.deepEqual(Object.keys(inputSchema.properties),['operation_id','reason','summary']);
  assert.throws(() => createManagedCallPlugin({nodePath:'node'}), /Invalid managed/);
});

test('valid owner paths/resolvers cannot activate a deferred undeployed contract',async()=>{
  const trap=()=>{throw Error('deferred contract touched runtime');};
  await createManagedCallPlugin({nodePath:process.execPath,codeRoot:path.resolve('.'),
    resolveCaller:trap,resolveGrant:trap}).setup(new Proxy({}, {get:trap}));
});

test('model overrides and native permission denial require no backend checkout', async () => {
  const binding = {nodePath:process.execPath,codeRoot:path.resolve('.'),
    resolveCaller:async () => {throw Error('must not resolve');},
    resolveGrant:async () => {throw Error('must not resolve');}};
  let permissions=0;
  const def = await tool(binding,async () => {permissions++;throw Error('native deny');});
  for (const key of ['role','session_id','project_id','directory','token','url','path','context'])
    assert.equal((await run(def,{...body(),[key]:'override'})).reason,'request-refused');
  assert.equal(permissions,0);
  await assert.rejects(run(def), /native deny/);
  assert.equal(permissions,1);
});

test('transport secrecy, bounds, cancellation and no automatic retry', async t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.resolve('.cf-')));
  t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  fs.mkdirSync(path.join(root,'bridge'));
  const entry = path.join(root,'bridge/reachout.mjs');
  const token = 'x'.repeat(43);
  const binding = {nodePath:process.execPath,codeRoot:root,resolveCaller:async () => caller,resolveGrant:async () => token};
  // This separate fault fixture inspects only synthetic secrets, never owner data.
  fs.writeFileSync(entry, `import fs from 'node:fs';import net from 'node:net';
    const p=new net.Socket({fd:3,readable:true,writable:false});let s='';p.on('data',b=>s+=b);p.on('end',()=>{
      const e=JSON.parse(s);fs.writeFileSync('proof.json',JSON.stringify({fd:e.token==='${token}',env:Object.keys(process.env),argv:process.argv,context:e.context}));
      console.log(JSON.stringify({version:1,operation_id:process.argv[4],state:'blocked',reason:'host-unavailable'}));process.exitCode=1;});`);
  const def = await tool(binding), b=body();
  assert.equal((await run(def,b)).reason,'host-unavailable');
  const proof = JSON.parse(fs.readFileSync(path.join(root,'proof.json')));
  assert.equal(proof.fd,true);
  // macOS may inject this system encoding key even with spawn env:{}.
  assert.deepEqual(proof.env.filter(k => k !== '__CF_USER_TEXT_ENCODING'),[]);
  assert.ok(!proof.argv.includes(token));
  assert.deepEqual(proof.context,caller);
  for (const script of ["console.log('secret');process.exitCode=1", "console.log('x'.repeat(3000))", "console.error('secret');setInterval(()=>{},1000)", "setInterval(()=>{},1000)"]) {
    fs.writeFileSync(entry,`import fs from 'node:fs';fs.appendFileSync('attempts','1');${script}`);
    fs.writeFileSync(path.join(root,'attempts'),'');
    // The owner contract permits 170s admission. Test caller cancellation here,
    // rather than treating the retired 5s transport timer as the current SLA.
    const started=Date.now(), value=await run(def,body(),{...runtime(),signal:AbortSignal.timeout(4500)});
    assert.equal(value.state,'unknown'); assert.ok(Date.now()-started<6500);
    assert.equal(fs.readFileSync(path.join(root,'attempts'),'utf8'),'1');
    assert.ok(!JSON.stringify(value).includes('secret'));
  }
  const controller=new AbortController();controller.abort();
  assert.equal((await run(def,body(),{...runtime(),signal:controller.signal})).reason,'request-refused');
  assert.equal(fs.readFileSync(path.join(root,'attempts'),'utf8'),'1');
  const pending = new AbortController();
  const cancelTimer=setTimeout(() => pending.abort(),150);
  try { assert.equal((await run(def,body(),{...runtime(),signal:pending.signal})).state,'unknown'); }
  finally { clearTimeout(cancelTimer); }
  const count=fs.readFileSync(path.join(root,'attempts'),'utf8');
  assert.equal(count,'11');
  const unavailable=await tool({...binding,resolveCaller:async () => new Promise(() => {})});
  assert.equal((await run(unavailable)).reason,'request-refused');
  assert.equal(fs.readFileSync(path.join(root,'attempts'),'utf8'),count);
});
