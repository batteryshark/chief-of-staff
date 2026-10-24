import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import winner
from role_contract import permissions, native_plan_edit_rule, native_plan_overlay, rule
spec = importlib.util.spec_from_file_location('binding_install', ROOT / 'scripts/install-role-binding.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RoleBindingInstall(unittest.TestCase):
    def test_global_grant_is_shadowed_then_narrow_overlay_repairs_new_plans(self):
        home, location = '/fixture/home', '/fixture/project'
        grant = native_plan_edit_rule(home)
        legacy = [r for r in permissions('lead', home, '/brief', location) if r != grant]
        custom = rule('edit', home + '/.config/openchamber/projects/blocked/*', 'deny')
        legacy.append(custom)
        old = {'agents': {'lead': {'permissions': legacy, 'description': 'preserve'},
                          'writer': {'model': 'untouched'}}, 'policies': [{'keep': True}]}
        global_rules = permissions('lead', home, '/brief')
        target = home + '/.config/openchamber/projects/new/plans/new.md'
        self.assertEqual(winner('edit', target, global_rules + legacy)['effect'], 'deny')
        new = native_plan_overlay(old, home)
        rules = new['agents']['lead']['permissions']
        self.assertEqual(rules[:2], [legacy[0], grant])
        self.assertEqual(rules[:1] + rules[2:], legacy)
        self.assertEqual(winner('edit', target, global_rules + rules)['effect'], 'allow')
        for path in (home + '/.config/openchamber/projects/blocked/plans/new.md',
                     target + '.env', target.replace('new.md', '.env.md'),
                     target.replace('.md', '.txt'), target.replace('/plans/', '/source/'),
                     '/foreign/PROJECT.md', 'src/main.py', '../../../.config/openchamber/projects/new/plans/new.md'):
            self.assertEqual(winner('edit', path, global_rules + rules)['effect'], 'deny', path)
        new['agents']['lead']['permissions'] = legacy
        self.assertEqual(new, old)

    def test_narrow_installer_preserves_bytes_metadata_and_skips_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / '.opencode/opencode.json'; target.parent.mkdir()
            before = b'{ "agents": {"lead": {"permissions": [{"resource":"*","effect":"deny","action":"edit"}, {"action":"edit","resource":"custom/*","effect":"deny"}]}, "writer": {"model":"keep"}}, "custom": "untouched" }\n'
            target.write_bytes(before); target.chmod(0o640)
            digest = hashlib.sha256(before).hexdigest()
            after = installer.plan_overlay_bytes(before, str(Path.home()))
            insertion = b', ' + json.dumps(native_plan_edit_rule(str(Path.home()))).encode()
            self.assertEqual(after.replace(insertion, b'', 1), before)
            with patch.object(installer, 'knowledge_plans', side_effect=AssertionError('no lookup')):
                self.assertEqual(installer.install_native_plan(root, digest, dry=True)['status'], 'would-update')
                self.assertEqual(target.read_bytes(), before)
                with self.assertRaises(ValueError): installer.install_native_plan(root, '0' * 64)
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(installer.install_native_plan(root, digest)['status'], 'updated')
                self.assertEqual(target.read_bytes(), after)
                self.assertEqual(target.stat().st_mode & 0o777, 0o640)
                post = hashlib.sha256(after).hexdigest()
                self.assertEqual(installer.install_native_plan(root, post)['status'], 'same')
                with self.assertRaises(ValueError): installer.install_native_plan(root, digest)

    def test_narrow_overlay_refuses_ambiguous_baseline_and_duplicate_json(self):
        deny = rule('edit', '*', 'deny')
        for rules in ([], [rule('edit', 'custom', 'deny'), deny], [deny, deny]):
            with self.assertRaises(ValueError):
                native_plan_overlay({'agents': {'lead': {'permissions': rules}}}, '/home')
        with self.assertRaises(ValueError):
            installer.plan_overlay_bytes(b'{"agents": {}, "agents": {}}', '/home')

    def test_new_project_then_new_native_plan_without_roster_enrollment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); location = root / 'brand-new'; location.mkdir()
            target = location / '.opencode/opencode.json'
            with patch.object(installer, 'knowledge_plans', return_value=[]):
                installer.install(location)
            plan = str(root / 'native/plans/new.md')
            before = json.loads(target.read_text())['agents']['lead']['permissions']
            self.assertEqual(winner('edit', plan, before)['effect'], 'deny')
            # Trusted Knowledge discovery after a Plan is created, not enrollment.
            with patch.object(installer, 'knowledge_plans', return_value=[plan]):
                installer.install(location)
            rules = json.loads(target.read_text())['agents']['lead']['permissions']
            self.assertEqual(winner('edit', plan, rules)['effect'], 'allow')
            self.assertEqual(winner('edit', str(root / 'native/plans/foreign.md'), rules)['effect'], 'deny')
            self.assertFalse((root / '.docket').exists())

    def test_normal_installer_binding_keeps_unrelated_config_and_exact_own_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); location = root / 'project'; location.mkdir()
            target = location / '.opencode/opencode.json'; target.parent.mkdir()
            old = {'plugins': ['keep'], 'agents': {'other': {'model': 'keep/model'}}}
            target.write_text(json.dumps(old)); before = target.read_bytes()
            plan = str(root / 'native/plans/exact.md')
            with patch.object(installer, 'knowledge_plans', return_value=[plan]) as lookup:
                self.assertEqual(installer.install(location, dry=True)['status'], 'would-update')
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(installer.install(location)['status'], 'updated')
                self.assertEqual(installer.install(location)['status'], 'same')
                lookup.assert_called_with(str(location), str(Path.home()))
            result = json.loads(target.read_text()); lead = result['agents']['lead']
            self.assertEqual(set(lead), {'permissions'})
            self.assertEqual(result['agents']['other'], old['agents']['other'])
            self.assertEqual(result['plugins'], old['plugins'])
            for path in ('LEAD.md', 'PROJECT.md', str(location / 'lead/log.md'), plan):
                self.assertEqual(winner('edit', path, lead['permissions'])['effect'], 'allow')
            for path in (str(root / 'foreign/LEAD.md'), str(root / 'native/plans/foreign.md'), 'src/x.rs'):
                self.assertEqual(winner('edit', path, lead['permissions'])['effect'], 'deny')
            self.assertFalse((root / '.docket').exists())

    def test_lookup_or_custom_role_failure_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with patch.object(installer, 'knowledge_plans', side_effect=ValueError('lookup refused')):
                with self.assertRaises(ValueError): installer.install(root)
            self.assertFalse((root / '.opencode').exists())
            target = root / '.opencode/opencode.json'; target.parent.mkdir()
            target.write_text('{"agents":{"lead":{"system":"custom"}}}')
            before = target.read_bytes()
            with patch.object(installer, 'knowledge_plans', return_value=[]):
                with self.assertRaises(ValueError): installer.install(root)
            self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__': unittest.main()
