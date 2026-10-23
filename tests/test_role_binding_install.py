import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import winner
spec = importlib.util.spec_from_file_location('binding_install', ROOT / 'scripts/install-role-binding.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RoleBindingInstall(unittest.TestCase):
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
