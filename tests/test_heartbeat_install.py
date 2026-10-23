import importlib.util
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('install_heartbeat', ROOT / 'scripts/install-heartbeat.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class HeartbeatInstall(unittest.TestCase):
    def test_canonical_policy_changes_only_exact_field_and_retires_receipted_staged_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve();chief=home/'.chief-of-staff';agents=chief/'.opencode/agents';agents.mkdir(parents=True)
            old=agents/'chief-reset-staged-20261022-final.md';old.write_text('---\nmode: primary\n---\n<!-- managed by chief-of-staff/install.sh; lean role -->\nOld chief\n')
            canonical=agents/'chief-of-staff.md';body='<!-- managed by chief-of-staff/install.sh; lean role -->\nCanonical chief\n'
            canonical.write_text('---\nmode: primary\n---\n'+body)
            receipt=chief/'.opencode/reset-install'/f'{old.stem}.json';receipt.parent.mkdir()
            receipt.write_text(json.dumps({'state':'installed','files':{str(old):old.read_text()}}))
            options=chief/'heartbeat/pilot-options.json';options.parent.mkdir()
            before={'chiefInstructionsFile':str(old),'enabled':True,'goalSessions':['ses_unchanged'],'holdBindings':{'exact':'unchanged'},'other':'preserved'}
            options.write_text(json.dumps(before))
            calls=[]
            def request(method,url):
                calls.append((method,url))
                return (200,{'data':{}}) if url=='/api/session/active' else (200,{'data':{'system':body}})
            parent=types.ModuleType('docket');parent.__path__=[];host=types.ModuleType('docket.host')
            host.configured_adapter=lambda:types.SimpleNamespace(_request=request)
            config={'chiefLocation':str(chief),'docketSource':'/unused'}
            with patch.object(Path,'home',return_value=home),patch.dict(sys.modules,{'docket':parent,'docket.host':host}):
                installer.run(config,'canonical-chief',dry=True);self.assertTrue(old.exists())
                installer.run(config,'canonical-chief')
            self.assertEqual(json.loads(options.read_text()),{**before,'chiefInstructionsFile':str(canonical)})
            self.assertFalse(old.exists());self.assertTrue(all(method=='GET' for method,url in calls))

    def test_maintenance_only_updates_owned_runtime_and_never_changes_options_or_topology(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve(); chief = home / '.chief-of-staff'; chief.mkdir()
            origin = home / 'reset'; origin.mkdir()
            (origin / 'LEAD.md').write_text('## Goal\nApproved scope.\n\n## Stop conditions\nKeep hold.\n')
            config = {'chiefLocation':str(chief), 'originDirectory':str(origin), 'originSession':'ses_origin',
                      'nativeVersion':'2.0.32', 'docketSource':'/existing/docket', 'standingSections':[],
                      'goalBinding':{'id':'stored-old-goal','objective':'','objectiveFile':True}}
            with patch.object(Path, 'home', return_value=home):
                _, planned = installer.plan(config, 'enable')
                paths = {p:text for p,text in planned.items() if '/skills/' not in str(p) and '/agents/' not in str(p)}
                for p,text in paths.items():
                    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
                skill=origin/'.opencode/skills/reset-worktree-safety/SKILL.md';skill.parent.mkdir(parents=True)
                skill.write_text('prior receipt-owned procedure\n');paths[skill]=skill.read_text()
                bus = home / '.local/share/chief-of-staff/heartbeat/bus.mjs'
                bus.write_text('// prior owned runtime\n')
                receipt = chief / 'archive/reset-fixture/install-owned.json'; receipt.parent.mkdir(parents=True)
                receipt.write_text(json.dumps({'after':{str(p):installer.sha256(p.read_bytes()) for p in paths}}))
                options = chief / 'heartbeat/pilot-options.json'; before = options.read_bytes()
                installer.run(config, 'maintenance')
                self.assertEqual(options.read_bytes(),before)
                self.assertEqual(bus.read_bytes(),(ROOT/'heartbeat/bus.mjs').read_bytes())
                self.assertEqual(skill.read_text(),installer.procedures(str(chief))['reset-worktree-safety'])
                self.assertFalse((origin/'.opencode/skills/reset-shape').exists())
                wrapper = (origin/'.opencode/plugins/chief-heartbeat-pilot.js').read_text()
                self.assertIn('options.reconciliationRequired = true',wrapper)
                self.assertIn(str(home/'.docket/lead-checkins.jsonl'),wrapper)
                self.assertFalse((origin/'.opencode/agents/lead.md').exists())
                changed = dict(config, postOnlyRecipients=[{'session':'ses_new','directory':str(origin)}])
                with self.assertRaisesRegex(ValueError,'topology'): installer.run(changed,'maintenance')
                bus.write_text('// unrelated change\n')
                with self.assertRaisesRegex(ValueError,'preserve/reconcile'): installer.run(config,'maintenance')
                bus.write_text((ROOT/'heartbeat/bus.mjs').read_text())
                skill.write_text('independent local procedure edit\n')
                with self.assertRaisesRegex(ValueError,'preserve/reconcile'):installer.run(config,'maintenance')
                self.assertEqual(skill.read_text(),'independent local procedure edit\n')
                skill.write_text(installer.procedures(str(chief))['reset-worktree-safety'])
                unowned=origin/'.opencode/skills/reset-reporting/SKILL.md';unowned.parent.mkdir(parents=True);unowned.write_text('unowned local instructions')
                with self.assertRaisesRegex(ValueError,'unowned local procedure'):installer.run(config,'maintenance')
                self.assertEqual(unowned.read_text(),'unowned local instructions')
                self.assertEqual(options.read_bytes(),before)

    def test_iphone_profile_is_incremental_post_only_without_expanding_policy_records(self):
        # Synthetic incremental manifests preserve the topology assertions without
        # publishing actual enrolled sessions, machines or migration receipts.
        old = json.loads((ROOT/'tests/fixtures/heartbeat/post-only-one.json').read_text())
        new = json.loads((ROOT/'tests/fixtures/heartbeat/post-only-two.json').read_text())
        self.assertEqual(new['base'], 'heartbeat-reset-pilot.json')
        self.assertEqual(new['migrationGate'], old['migrationGate'])
        self.assertEqual(new['postOnlyRecipients'][:-1], old['postOnlyRecipients'])
        self.assertEqual(new['postOnlyRecipients'][-1], {
            'session':'ses_project_two',
            'directory':'/fixture/project-two',
            'standingSections':[]})
        self.assertNotIn('goalBinding', new)
        self.assertNotIn('goalSessions', new)

    def test_mac_profile_preserves_iphone_and_dream_without_new_goal_or_policy_bindings(self):
        old = json.loads((ROOT/'tests/fixtures/heartbeat/post-only-two.json').read_text())
        new = json.loads((ROOT/'tests/fixtures/heartbeat/post-only-three.json').read_text())
        self.assertEqual(new['migrationGate'], old['migrationGate'])
        self.assertEqual(new['postOnlyRecipients'][:-1], old['postOnlyRecipients'])
        self.assertEqual(new['postOnlyRecipients'][-1], {
            'session':'ses_project_three',
            'directory':'/fixture/project-three',
            'standingSections':[]})
        self.assertNotIn('goalBinding', new)
        self.assertNotIn('goalSessions', new)

    def test_prepare_is_disabled_backed_up_and_never_changes_global_roles_or_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve(); chief = home / 'chief'; chief.mkdir(); origin = home / 'reset'; origin.mkdir()
            (origin / 'LEAD.md').write_text('## Goal\nReal approved scope.\n\n## Stop conditions\nKeep explicit hold.\n')
            helper = home / '.local/bin/chief-nod'; helper.parent.mkdir(parents=True)
            helper.write_text('# managed by chief-of-staff/install.sh\nlegacy bytes\n'); helper.chmod(0o755)
            global_role = home / '.config/opencode/agents/lead.md'; global_role.parent.mkdir(parents=True)
            global_role.write_text('other project shared role')
            config = {'chiefLocation':str(chief),'originDirectory':str(origin),'originSession':'ses_origin','nativeVersion':'2.0.32',
                      'docketSource':'/existing/docket','standingSections':[], 'goalBinding':{'id':'owned','objective':'','objectiveFile':True}}
            with patch.object(Path, 'home', return_value=home):
                with self.assertRaisesRegex(ValueError, 'real-call fixture matrix'):
                    installer.run(config, 'prepare')
                _, files = installer.plan(config, 'prepare')
                options = json.loads(files[chief / 'heartbeat/pilot-options.json'])
                self.assertFalse(options['enabled']); self.assertFalse(options['nodSendEnabled'])
                self.assertEqual(options['holdBindings'][str(origin)]['global'][0]['allowedQuote'],'Keep explicit hold.')
                self.assertFalse((origin / '.opencode/agents/lead.md').exists())
                self.assertFalse((origin / '.opencode/opencode.json').exists())
                with self.assertRaises(ValueError): installer.run(config,'attention')  # maintenance cannot enable/change topology
                self.assertFalse((chief/'heartbeat/pilot-options.json').exists())
                self.assertEqual(helper.read_text(),'# managed by chief-of-staff/install.sh\nlegacy bytes\n')
                self.assertEqual(global_role.read_text(),'other project shared role')
                self.assertFalse((home / '.local/share/chief-of-staff/heartbeat/integration.test.mjs').exists())
                with self.assertRaises((ValueError, OSError)): installer.run(config,'roles')
                effective = home / '.config/openchamber/goals/ses_origin.md'; effective.parent.mkdir(parents=True)
                effective.write_text('Goal: real approved scope.\n')
                config['goalBinding'].update(objectiveFilePath=str(effective), effectiveObjectiveSha256=hashlib.sha256(b'Goal: real approved scope.').hexdigest())
                installer.plan(config, 'enable')  # Authorized file-mode enrichment, no goal/state edit.
                effective.write_text('Goal: different scope.\n')
                with self.assertRaises(ValueError): installer.plan(config,'enable')
                effective.write_text('Goal: real approved scope.\n')
                dream = home / 'dream'; dream.mkdir()
                config['postOnlyRecipients'] = [{'session':'ses_dream','directory':str(dream),'standingSections':[]}]
                with self.assertRaisesRegex(ValueError,'retired local-role'):installer.plan(config,'roles')
                config['leadMemoryBindings']={str(origin):{'planFiles':[]},str(dream):{'planFiles':[]}}
                _, planned = installer.plan(config, 'prepare')
                scoped = json.loads(planned[chief / 'heartbeat/pilot-options.json'])
                self.assertEqual(scoped['originSessions'],['ses_origin','ses_dream'])
                self.assertEqual(scoped['goalSessions'],['ses_origin'])
                self.assertNotIn(str(dream),scoped['holdBindings'])
                self.assertFalse((dream / '.opencode').exists())
                config.pop('postOnlyRecipients')
                (origin / 'LEAD.md').write_text('## Goal\nReal approved scope.\n\n## Stop conditions\nNew hold.\n')
                with self.assertRaises(ValueError): installer.run(config,'enable')
