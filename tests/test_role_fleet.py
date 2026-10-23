import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('role_fleet', ROOT / 'scripts/install-role-fleet.py')
fleet = importlib.util.module_from_spec(spec); spec.loader.exec_module(fleet)


class RoleFleet(unittest.TestCase):
    def test_known_owned_migration_retains_native_state_and_does_not_enroll_extra_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve(); project = home / 'project'; project.mkdir()
            repair = home / 'repair'; repair.mkdir()
            source = home / 'source'; source.mkdir()
            for name in ('milestone.py', 'checkins.py', 'parse.py', '__init__.py'):
                path = source / 'docket' / name; path.parent.mkdir(exist_ok=True); path.write_text('# fixture\n')
            roster = home / '.docket/lead-checkins.jsonl'; roster.parent.mkdir()
            raw = json.dumps({'session': 'ses_lead', 'directory': str(project), 'state': 'active'}) + '\n'
            roster.write_text(raw)
            native = {'id': 'ses_lead', 'agent': 'lead', 'location': {'directory': str(project)},
                      'model': {'providerID': 'fixture', 'id': 'same', 'variant': 'high'},
                      'metadata': {'openchamber': {'goal': {'objective': 'Keep exact outcome.', 'status': 'active'}}}}
            calls = []
            def request(method, url):
                calls.append((method, url)); return 200, {'data': json.loads(json.dumps(native))}
            host = types.ModuleType('docket.host'); host.configured_adapter = lambda: types.SimpleNamespace(_request=request)
            parent = types.ModuleType('docket'); parent.__path__ = []
            local = project / '.opencode/agents/lead.md'; local.parent.mkdir(parents=True)
            rules = [{'action': 'edit', 'resource': '*', 'effect': 'deny'},
                     {'action': 'edit', 'resource': '*/LEAD.md', 'effect': 'allow'},
                     {'action': 'shell', 'resource': 'rm *', 'effect': 'ask'}]
            local.write_text('---\npermissions: ' + json.dumps(rules) + '\n---\n<!-- managed by chief-of-staff/install.sh -->\n# Lead\n')
            wrapper = project / '.opencode/plugins/docket-own-milestone.js'; wrapper.parent.mkdir()
            wrapper.write_text('// known installed fixture\n')
            receipt = home / '.chief-of-staff/archive/reset-test/install-test.json'; receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'after': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (local, wrapper)}}))
            with patch.object(Path, 'home', return_value=home), patch.dict(sys.modules, {'docket': parent, 'docket.host': host}), patch.object(fleet, 'knowledge_plans', return_value=[]):
                self.assertEqual(fleet.migrate(source, [repair], dry=True)['status'], 'would-update')
                self.assertTrue(local.exists())
                result = fleet.migrate(source, [repair])
                self.assertEqual(result['status'], 'updated')
                self.assertEqual(len(result['callers']), 1)
            self.assertEqual(roster.read_text(), raw)
            self.assertTrue(all(method == 'GET' for method, _ in calls))
            self.assertFalse(local.exists()); self.assertFalse(wrapper.exists())
            self.assertTrue((project / '.opencode/retired-role-artifacts/.opencode/agents/lead.md').exists())
            self.assertTrue((home / '.config/opencode/plugins/chief-own-milestone.js').exists())
            config = json.loads((repair / '.opencode/opencode.json').read_text())
            self.assertEqual(set(config['agents']['lead']), {'permissions'})

    def test_independent_unknown_local_edit_grant_refuses(self):
        text = '---\npermissions: [{action: edit, resource: "foreign/*", effect: allow}]\n---\nowned\n'
        with self.assertRaises(ValueError): fleet.retained_local_rules(text, '/project', [], '/brief')


if __name__ == '__main__': unittest.main()
