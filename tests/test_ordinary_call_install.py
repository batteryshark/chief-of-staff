"""Offline registration/install tests only. The owner CLI is never executed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('ordinary_install', ROOT / 'scripts/install-ordinary-call.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
sha = lambda data: hashlib.sha256(data).hexdigest()


class OrdinaryCallInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve(); self.chief = self.home / '.chief-of-staff'
        self.wrapper = self.chief / '.opencode/plugins/chief-ordinary-call.js'; self.wrapper.parent.mkdir(parents=True)
        self.wrapper.write_text('// receipt-owned legacy fixture\nexport default {setup(ctx){if(ctx.app.version!=="2.0.32")return;}};\n')
        self.wrapper.chmod(0o640); (self.wrapper.parent / 'package.json').write_text('{"type":"module"}')
        self.module = self.home / '.local/share/chief-of-staff/voicestack/ordinary-call.mjs'; self.module.parent.mkdir(parents=True)
        self.module.write_bytes((ROOT / 'services/voicestack/ordinary-call.mjs').read_bytes())
        self.version = self.home / '.local/share/chief-of-staff/heartbeat/version.mjs'; self.version.parent.mkdir(parents=True)
        self.version.write_bytes((ROOT / 'heartbeat/version.mjs').read_bytes())
        self.code = self.home / 'owner'; (self.code / 'bridge').mkdir(parents=True)
        self.cli = self.code / 'bridge/reachout.mjs'
        self.cli.write_text('throw Error("OWNER CLI MUST NEVER EXECUTE IN REGISTRATION TEST");\n')
        self.attempts = self.chief / 'ordinary-call-attempts'; self.attempts.mkdir(mode=0o700)
        (self.attempts / 'retained.json').write_text('{"historical":"unchanged"}')
        self.binding = {'nodePath': shutil.which('node'), 'codeRoot': str(self.code),
                        'chiefPointerFile': str(self.chief / 'chief.json'), 'directory': str(self.chief),
                        'agentID': 'chief-of-staff', 'attemptDirectory': str(self.attempts), 'cliSha256': sha(self.cli.read_bytes())}
        (self.chief / 'chief.json').write_text(json.dumps({'session':'ses_nativechief','directory':str(self.chief)}))
        (self.chief / 'heartbeat').mkdir(); (self.chief / 'heartbeat/pilot-options.json').write_text('{"holds":"unchanged"}')
        (self.chief / '.opencode/agents').mkdir(); (self.chief / '.opencode/agents/chief-of-staff.md').write_text('current chief permissions/body')
        (self.chief / '.opencode/opencode.json').write_text('{"permissions":[]}')
        self.status = self.chief / '.opencode/reset-install/ordinary-call-runtime.json'; self.status.parent.mkdir()
        self.status.write_text('{"pid":"stale receipt preserved until native registration"}')
        self.original = self.chief / 'archive/reset-20261022-heartbeat/install-ordinary-call-20261022.json'; self.original.parent.mkdir(parents=True)
        self.original.write_text(json.dumps({'scope':'ordinary-chief-call-only','binding':self.binding,
            'after':{str(p):sha(p.read_bytes()) for p in (self.wrapper,self.module)}}))

    def call(self, revision='case20', dry=False):
        with patch.object(Path, 'home', return_value=self.home):
            return installer.install(self.chief, revision, dry)

    def protected(self):
        return {str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file() and p != self.wrapper
                and 'reset-ordinary-call-maintenance' not in str(p)}

    def test_normal_entry_dry_run_and_exact_immutable_owned_update(self):
        protected=self.protected(); before=self.wrapper.read_bytes()
        result=subprocess.run(['bash',str(ROOT/'install.sh'),'--ordinary-call-maintenance',str(self.chief),
                               '--revision','case20','--dry-run'],env={**os.environ,'HOME':str(self.home)},
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'would-update')
        self.assertEqual(self.wrapper.read_bytes(),before);self.assertEqual(self.protected(),protected)
        self.assertFalse((self.chief/'archive/reset-ordinary-call-maintenance').exists())
        installed=self.call();self.assertEqual(installed['changedTargets'],[str(self.wrapper)])
        self.assertEqual(installed['binding'],self.binding);self.assertFalse(installed['ownerCLIExecuted'])
        self.assertEqual(Path(installed['backup']).read_bytes(),before)
        self.assertEqual(self.wrapper.stat().st_mode&0o777,0o640)
        self.assertEqual(self.protected(),protected)
        self.assertIn("!atLeast(ctx.app.version,'2.0.32')",self.wrapper.read_text())
        self.assertEqual(self.call()['status'],'same')
        self.wrapper.write_bytes(before)
        with self.assertRaisesRegex(ValueError,'archive collision'):self.call()
        self.assertEqual(self.wrapper.read_bytes(),before)

    def test_unknown_or_modified_ownership_dependencies_and_revision_refuse(self):
        before=self.wrapper.read_bytes()
        for revision in ('','..','../escape','/absolute','a/b','a\\b','a\nnext'):
            with self.assertRaisesRegex(ValueError,'revision'):self.call(revision)
            self.assertEqual(self.wrapper.read_bytes(),before)
        self.wrapper.write_bytes(before+b'// independent edit\n')
        with self.assertRaisesRegex(ValueError,'receipt-owned'):self.call()
        self.wrapper.write_bytes(before)
        self.cli.write_text('independent owner update')
        with self.assertRaisesRegex(ValueError,'CLI changed'):self.call()
        self.assertEqual(self.wrapper.read_bytes(),before)
        self.assertFalse((self.chief/'archive/reset-ordinary-call-maintenance').exists())

    def test_symlink_and_missing_original_receipt_cannot_adopt_installed_bytes(self):
        original=self.original.read_bytes();self.original.unlink()
        with self.assertRaises(FileNotFoundError):self.call()
        self.original.write_bytes(original)
        before=self.wrapper.read_bytes();self.wrapper.unlink();self.wrapper.symlink_to(self.cli)
        with self.assertRaisesRegex(ValueError,'symlink'):self.call()
        self.assertEqual(self.cli.read_bytes(),b'throw Error("OWNER CLI MUST NEVER EXECUTE IN REGISTRATION TEST");\n')

    def test_reviewed_runtime_and_version_dependency_drift_refuse_without_replacement(self):
        before=self.wrapper.read_bytes()
        for target in (self.module,self.version):
            original=target.read_bytes();target.write_bytes(original+b'// changed independently\n')
            with self.assertRaisesRegex(ValueError,'drift|reviewed installed'):self.call()
            self.assertEqual(self.wrapper.read_bytes(),before)
            self.assertFalse((self.chief/'archive/reset-ordinary-call-maintenance').exists())
            target.write_bytes(original)

    def test_expected_current_pointer_change_refuses_before_backup_or_entry_write(self):
        before=self.wrapper.read_bytes();render=installer.render
        def concurrent_change(*args):
            (self.chief/'chief.json').write_text('{"session":"ses_other","directory":"/moved"}')
            return render(*args)
        with patch.object(installer,'render',side_effect=concurrent_change):
            with self.assertRaisesRegex(ValueError,'expected installed bytes changed'):self.call()
        self.assertEqual(self.wrapper.read_bytes(),before)
        self.assertFalse((self.chief/'archive/reset-ordinary-call-maintenance').exists())

    def test_generated_wrapper_registers_on_2_1_3_and_refuses_unsupported_without_execution(self):
        self.call();protected=self.protected()
        script=r'''
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [wrapper,status,directory]=process.argv.slice(1);
const plugin=(await import(pathToFileURL(wrapper).href)).default;
for(const [version,location,expected] of [['2.0.32',directory,true],['2.1.3',directory,true],
 ['2.0.31',directory,false],['2.0.0',directory,false],['2.1.3-beta',directory,false],
 ['v2.1.3',directory,false],['2.1',directory,false],['unknown',directory,false],['2.1.3','/foreign',false]]){
  await writeFile(status,'stale prior registration');let definitions=[],nativeReads=0,permissionChecks=0,disposed=0;
  const ctx={app:{version},location:{directory:location},
    session:{get:async()=>{nativeReads++;throw Error('NO native execution in registration proof');}},
    permission:{assert:async()=>{permissionChecks++;throw Error('NO call permission request');}},
    tool:{transform:async fn=>{fn({add:d=>definitions.push(d)});return{dispose(){disposed++;}};},
          list:async()=>definitions.map(d=>({...d,id:d.name}))}};
  const stop=await plugin.setup(ctx);
  assert.equal(definitions.length,expected?1:0,version+' '+location);
  assert.equal(nativeReads,0);assert.equal(permissionChecks,0);
  if(expected){const value=JSON.parse(await readFile(status,'utf8'));assert.equal(value.version,version);
    assert.equal(value.pid,process.pid);assert.equal(value.tool,'chief_urgent_call');assert.equal(value.managedAvailable,false);
    assert.deepEqual(value.input.properties.reason.enum,['decision','goal-risk']);
    assert.equal(value.input.properties.title.maxLength,100);assert.equal(value.input.properties.body.maxLength,1000);
    assert.equal(typeof definitions[0].execute,'function'); // deliberately NEVER called
    await stop();assert.equal(disposed,1);
  }else{assert.equal(await readFile(status,'utf8'),'stale prior registration');assert.equal(disposed,0);}
}
console.log('registration-only: current/floor pass; older/malformed/prerelease/foreign refuse; zero executions');
'''
        result=subprocess.run(['node','--input-type=module','-e',script,str(self.wrapper),str(self.status),str(self.chief)],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('zero executions',result.stdout)
        # Only the synthetic registration receipt is permitted to change.
        after=self.protected();protected.pop(str(self.status));after.pop(str(self.status))
        self.assertEqual(after,protected)


if __name__ == '__main__': unittest.main()
