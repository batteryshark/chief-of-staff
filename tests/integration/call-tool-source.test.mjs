import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createNativeManagedCallPlugin} from '../../services/voicestack/opencode.js';

// Deferred branch ONLY, not the deployed ordinary-call contract at a181b63.
const modules = ['reachout.mjs','managed-call.mjs','reachout-policy.mjs','push-store.mjs','dev-override.mjs','open-voice-admin.mjs','open-voice-caller-authority.mjs','managed-owner-binding.mjs'];
// Explicit reviewed repository root and commit, used ONLY to copy fixture source.
// Never a production binding, credential source or child environment setting.
const sourceRoot = process.env.CALL_TOOL_TEST_SOURCE;
if (!sourceRoot || !path.isAbsolute(sourceRoot)) throw new Error('Set CALL_TOOL_TEST_SOURCE to an absolute reviewed product source root containing bridge/.');
const sourceRef = process.env.CALL_TOOL_TEST_REF;
if (sourceRef!=='866cc313166854e93ce5838e39805d726f290903') throw new Error('Deferred managed-call fixture requires exact owner-reviewed 866cc313166854e93ce5838e39805d726f290903');
if (!sourceRef || !/^[0-9a-f]{7,40}$/.test(sourceRef)) throw new Error('Set CALL_TOOL_TEST_REF to the reviewed product commit hash (7–40 lowercase hex characters).');
const git = args => execFileSync('git',['-C',sourceRoot,...args],{encoding:'utf8',timeout:5000,maxBuffer:262144});
const commit = git(['rev-parse','--verify',`${sourceRef}^{commit}`]).trim();
// Read all eight exact deferred blobs before creating scratch. No checkout/fetch/write,
// mutable working-file fallback, permanent vendoring or production binding.
const sources = new Map(modules.map(name => [name,git(['show','--no-ext-diff','--no-textconv',`${commit}:bridge/${name}`])]));
const caller = {version:1,role:'chief',session_id:'ses_fixtureExisting',agent_id:'build',project_id:'fixture-project',directory:'/synthetic/project'};
const runtime = () => ({sessionID:caller.session_id,agent:'build',messageID:'msg_fixture',id:'call_fixture',signal:new AbortController().signal});
const body = () => ({operation_id:randomUUID(),reason:'decision',summary:'Fixture choice'});
async function tool(binding, get, permission = async () => {}) {
  let definition;
  await createNativeManagedCallPlugin(binding).setup({
    get location(){throw Error('plugin location must not be consulted');},
    session:{get},permission:{assert:permission},tool:{transform:async cb => cb({add:d => {definition=d;}})}});
  return definition;
}
const run = async (t,b=body(),c=runtime()) => JSON.parse((await t.execute(b,c)).content);

test('native metadata + real owner binding + CLI/admin: authenticated blocked, fresh refusal, no call effects', async t => {
  // Only these eight reviewed deferred files and their built-in imports are copied.
  const root = fs.realpathSync(fs.mkdtempSync(path.resolve('.cf-')));
  fs.chmodSync(root,0o700);
  let admin;
  t.after(async () => {if (admin) await admin.close(); fs.rmSync(root,{recursive:true,force:true});});
  fs.mkdirSync(path.join(root,'bridge'));
  for (const name of modules)
    fs.writeFileSync(path.join(root,'bridge',name),sources.get(name));
  const load = name => import(pathToFileURL(path.join(root,'bridge',name)));
  const {PushStore} = await load('push-store.mjs');
  const {ReusableCallerAuthority} = await load('open-voice-caller-authority.mjs');
  const {startOpenVoiceAdmin} = await load('open-voice-admin.mjs');
  const {createManagedCallerResolvers,provisionManagedCaller,revokeManagedCaller} = await load('managed-owner-binding.mjs');
  fs.mkdirSync(path.join(root,'private'),{mode:0o700});
  const store = new PushStore(path.join(root,'private/push'));
  let requests=0, now=Date.now();
  const control = {state:store.openVoice(),now:() => now,principal_id:'fixture-principal',audience:'fixture-bridge',
    room(){},save(){store.save();},push:{serial:async cb => cb()}};
  // eb7eb71 missing production host refuses before reservation/preparation.
  control.reusableCallers = new ReusableCallerAuthority(control);
  const authenticate=control.reusableCallers.authenticateManaged.bind(control.reusableCallers);
  control.reusableCallers.authenticateManaged = value => {requests++;return authenticate(value);};
  const authorization = {version:1,caller_id:'fixture-caller',binding:caller,
    scopes:['call:request','call:status:own'],approval_ref:'synthetic-only',approved_at:now,expires_at:null};
  // New synthetic receipt only. No production issuance, provisioning or reads.
  const grant = control.reusableCallers.issue(authorization);
  provisionManagedCaller({codeRoot:root,receipt:grant,authorization,expectedRevision:0,now:() => now});
  const lead = {...caller,role:'lead',session_id:'ses_fixtureLead'};
  const leadAuthorization = {...authorization,caller_id:'fixture-lead',binding:lead,expires_at:now+1000};
  const leadGrant = control.reusableCallers.issue(leadAuthorization);
  provisionManagedCaller({codeRoot:root,receipt:leadGrant,authorization:leadAuthorization,expectedRevision:1,now:() => now});
  const before = fs.readFileSync(store.file,'utf8');
  const bindingFile=path.join(store.directory,'managed-bindings-v1.json');
  const ownerBefore=fs.readFileSync(bindingFile,'utf8');
  admin = await startOpenVoiceAdmin(control,store.directory);
  const ownerResolvers=createManagedCallerResolvers({codeRoot:root,now:() => now});
  const binding = {nodePath:process.execPath,codeRoot:root,ownerResolvers,fixtureOnly:true};
  let permissions=0, reads=0, native={id:caller.session_id,agent:caller.agent_id,projectID:caller.project_id,location:{directory:caller.directory}};
  const get=async ({sessionID},{signal}) => {reads++; assert.equal(sessionID,native.id);assert.equal(signal.aborted,false);return native;};
  const def = await tool(binding,get, async p => {permissions++; assert.equal(p.action,'chief_call');assert.equal(p.sessionID,native.id);});
  assert.equal(requests,0); assert.equal(reads,0); // setup never probes
  const b = body();
  const accepted=await run(def,b);
  assert.deepEqual(accepted,{version:1,operation_id:b.operation_id,state:'blocked',reason:'host-unavailable'});
  assert.equal(requests,1); assert.equal(permissions,1);
  // The composition defensively clones the real approved Chief context before
  // real resolveGrant; successful backend auth proves the clone is accepted.
  // Agent is "build", not a role name; only the approved record supplies Chief.
  assert.ok(!JSON.stringify(accepted).includes(grant.token));
  assert.ok(!JSON.stringify(accepted).includes(caller.session_id));
  for (const key of ['role','session_id','project_id','directory','token','url','path','context']) {
    assert.equal((await run(def,{...body(),[key]:'override'})).reason,'request-refused');
  }
  assert.equal(requests,1); assert.equal(permissions,1);
  native={...native,location:{directory:'/wrong'}};
  assert.equal((await run(def)).reason,'request-refused');
  native={...native,location:{directory:caller.directory}};
  assert.equal(requests,1);
  await assert.rejects(run(await tool(binding,get,async () => {throw Error('native deny');})), /native deny/);
  const quartet={session_id:caller.session_id,agent_id:caller.agent_id,project_id:caller.project_id,directory:caller.directory};
  const context=ownerResolvers.resolveCaller(quartet);
  assert.equal(context.role,'chief');
  assert.throws(() => ownerResolvers.resolveGrant(Object.freeze({...context,role:'lead'})),{message:'managed binding unavailable'});
  assert.throws(() => ownerResolvers.resolveGrant(Object.freeze({...context,directory:'/wrong'})),{message:'managed binding unavailable'});
  // Same native agent, different approved record: Lead is valid before expiry.
  native={...native,id:lead.session_id};
  const leadRuntime={...runtime(),sessionID:lead.session_id};
  assert.equal((await run(def,body(),leadRuntime)).reason,'host-unavailable');
  assert.equal(requests,2);
  now+=1001;
  assert.equal((await run(def,body(),leadRuntime)).reason,'request-refused');
  assert.equal(requests,2);
  native={...native,id:caller.session_id};
  // Missing store is a local sanitized refusal; restore the same synthetic file.
  fs.renameSync(bindingFile,bindingFile+'.held');
  try {assert.equal((await run(def)).reason,'request-refused');}
  finally {fs.renameSync(bindingFile+'.held',bindingFile);}
  assert.equal(requests,2);
  assert.equal(fs.readFileSync(store.file,'utf8'),before);
  assert.equal(fs.readFileSync(bindingFile,'utf8'),ownerBefore);
  assert.deepEqual(control.state.callerOperationsV1,{});
  // Revoke between the real caller and grant callbacks: a fresh lookup must
  // refuse the defensive clone, rather than reuse the previously read token.
  const racing=await tool({...binding,ownerResolvers:{
    resolveCaller(q,opts){const c=ownerResolvers.resolveCaller(q,opts);
      revokeManagedCaller({codeRoot:root,grant_id:grant.grant_id,expectedRevision:2,now:() => now});return c;},
    resolveGrant:ownerResolvers.resolveGrant,
  }},get);
  assert.equal((await run(racing)).reason,'request-refused');
  const revokedSnapshot=fs.readFileSync(bindingFile,'utf8');
  assert.equal((await run(def)).reason,'request-refused');
  assert.equal(fs.readFileSync(bindingFile,'utf8'),revokedSnapshot);
  assert.equal(fs.readFileSync(store.file,'utf8'),before);
  assert.equal(requests,2); assert.deepEqual(control.state.callerOperationsV1,{});
});
