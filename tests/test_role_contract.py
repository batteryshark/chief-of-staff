import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from role_contract import permissions, project_config, agent, knowledge_plans
from role_cleanup import retire
from role_contract import authorized_project_docs
from access_policy import winner


class Contract(unittest.TestCase):
    def test_global_native_plan_edit_grant_and_boundaries(self):
        home = '/Users/fixture'
        root = home + '/.config/openchamber/projects/'
        rules = permissions('lead', home, '/brief')
        grant = dict(action='edit', resource=root + '*/plans/*.md', effect='allow')
        self.assertEqual(rules.count(grant), 1)
        for project in ('own', 'foreign'):
            self.assertEqual(winner('edit', root + project + '/plans/new.md', rules)['effect'], 'allow')
        for path in (root + 'own/context.json', root + 'own/plans/new.txt',
                     root + 'own/plans/new.md.env', root + 'own/plans/.env.md',
                     root + 'own/source/main.md', '/outside/projects/own/plans/new.md',
                     '/other' + root + 'own/plans/new.md', '/foreign/PROJECT.md', 'src/main.py'):
            with self.subTest(path=path):
                self.assertEqual(winner('edit', path, rules)['effect'], 'deny')
        for role in ('chief', 'dispatcher'):
            self.assertNotIn(grant, permissions(role, home, '/brief'))

    def test_root_and_nested_private_key_normalization(self):
        rules = permissions('lead', '/Users/fixture', '/brief', '/fixture/a')
        for action in ('read', 'edit'):
            for resource in ('mock.key', 'mock.pem', 'lead/mock.key', '/fixture/a/mock.pem'):
                self.assertEqual(winner(action, resource, rules)['effect'], 'deny')

    def test_chief_cross_project_docs_from_enrolled_native_bindings(self):
        row = dict(session='ses_project', directory='/fixture/a', state='hold')
        native = dict(id='ses_project', agent='lead', location=dict(directory='/fixture/a'))
        docs = authorized_project_docs([row], [native])
        rules = permissions('chief', '/Users/fixture', '/fixture/chief', '/fixture/chief', project_docs=docs)
        for target in ('/fixture/a/PROJECT.md', '../a/PROJECT.md'):
            self.assertEqual(winner('edit', target, rules)['effect'], 'allow')
        for target in ('/fixture/a/src/a.rs', '/fixture/b/PROJECT.md'):
            self.assertEqual(winner('edit', target, rules)['effect'], 'deny')
        with self.assertRaises(ValueError):
            authorized_project_docs([{**row, 'directory': '/foreign'}], [native])
        with self.assertRaises(ValueError):
            authorized_project_docs([row], [{**native, 'time': {'archived': 1}}])
        with self.assertRaises(ValueError):
            permissions('lead', '/Users/fixture', '/brief', '/fixture/a', project_docs=docs)

    def effect(self, action, path):
        return winner(action, path, permissions('lead', '/Users/fixture', '/Users/fixture/.chief-of-staff',
            '/fixture/a', ['/Users/fixture/.config/openchamber/projects/a/plans/one.md']))['effect']

    def test_exact_own_and_foreign(self):
        for target in ('LEAD.md', 'PROJECT.md', 'lead/a/b.md', '/fixture/a/LEAD.md'):
            self.assertEqual(self.effect('edit', target), 'allow')
        for target in ('/fixture/b/LEAD.md', 'src/x.rs', 'lead/k.env', 'lead/.env.local',
                       '/Users/fixture/.chief-of-staff/secrets/key', '/Users/fixture/.docket/lead-checkins.jsonl'):
            self.assertEqual(self.effect('edit', target), 'deny')
        self.assertEqual(self.effect('edit', '/Users/fixture/.config/openchamber/projects/a/plans/one.md'), 'allow')
        self.assertEqual(self.effect('edit', '/Users/fixture/.config/openchamber/projects/b/plans/one.md'), 'allow')
        self.assertEqual(self.effect('shell', 'rm -rf fixture'), 'ask')
        self.assertEqual(self.effect('docket_milestone', 'own'), 'allow')

    def test_dispatcher(self):
        rules = permissions('dispatcher', '/Users/fixture', '/brief')
        self.assertEqual(winner('heartbeat_resolve', 'id', rules)['effect'], 'allow')
        self.assertEqual(winner('read', 'anything', rules)['effect'], 'deny')

    def test_project_permission_only_merge(self):
        old = {'plugins': ['unrelated'], 'agents': {'other': {'model': 'unchanged'}, 'lead': {
            'permissions': [{'action': 'shell', 'resource': 'custom*', 'effect': 'deny'}]}}}
        result = project_config(old, 'lead', '/Users/fixture', '/brief', '/fixture/a', [])
        self.assertEqual(result['plugins'], old['plugins'])
        self.assertEqual(result['agents']['other'], old['agents']['other'])
        self.assertEqual(set(result['agents']['lead']), {'permissions'})
        self.assertIn(old['agents']['lead']['permissions'][0], result['agents']['lead']['permissions'])
        self.assertEqual(old['agents']['lead']['permissions'][0]['resource'], 'custom*')
        with self.assertRaises(ValueError):
            project_config({'agents': {'lead': {'system': 'custom'}}}, 'lead', '/Users/fixture', '/brief', '/fixture/a', [])

    def test_globals_embed_only_location_relative_project_grants(self):
        text = agent('lead', '/Users/fixture', '/brief')
        self.assertNotIn('*/LEAD.md', text)
        self.assertIn('resource": "LEAD.md', text)
        self.assertNotIn('general access', text)

    def test_cleanup_preserves_unrelated_and_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / '.opencode/plugins'; folder.mkdir(parents=True)
            retired = folder / 'docket-own-milestone.js'; retired.write_text('known owned')
            keep = folder / 'chief-ordinary-call.js'; keep.write_text('keep')
            history = root / 'memory-access-proof.json'; history.write_text('historical data')
            known = {str(retired.relative_to(root)): hashlib.sha256(retired.read_bytes()).hexdigest()}
            retire(root, known)
            self.assertFalse(retired.exists()); self.assertEqual(keep.read_text(), 'keep')
            self.assertEqual(history.read_text(), 'historical data')
            retired.write_text('changed')
            with self.assertRaises(ValueError): retire(root, known)
            self.assertEqual(retired.read_text(), 'changed')

    def test_no_model_plan_override_or_auth_fallback(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(KeyError): knowledge_plans('/fixture/a', '/Users/fixture')

    def test_named_obsolete_shims_are_removed_not_rearchived_and_history_stays(self):
        from role_cleanup import remove_shims
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve(); project=home/'project'
            shim=project/'.opencode/plugins/own-plan-checkbox.js'; shim.parent.mkdir(parents=True); shim.write_text('owned shim')
            archive=project/'.opencode/retired-role-artifacts/.opencode/plugins/own-plan-checkbox.js'
            archive.parent.mkdir(parents=True); archive.write_text('owned shim')
            evidence=project/'plan-checkbox-evidence.json'; evidence.write_text('historical evidence')
            foreign=shim.with_name('foreign.js'); foreign.write_text('foreign')
            known={str(shim):{hashlib.sha256(shim.read_bytes()).hexdigest()}}
            self.assertEqual(len(remove_shims(home,known,dry=True)),2); self.assertTrue(shim.exists())
            remove_shims(home,known); self.assertFalse(shim.exists()); self.assertFalse(archive.exists())
            self.assertEqual(evidence.read_text(),'historical evidence'); self.assertEqual(foreign.read_text(),'foreign')
            shim.write_text('independent edit')
            with self.assertRaises(ValueError): remove_shims(home,known)


if __name__ == '__main__': unittest.main()
