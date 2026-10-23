import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from role_contract import shell_wrapper_policy

spec = importlib.util.spec_from_file_location('shell_policy_install', ROOT / 'scripts/install-shell-policy.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ShellPolicy(unittest.TestCase):
    def test_only_exact_wrapper_policies_no_permission_or_plugin_widening(self):
        old = {'plugins': ['other'], 'agents': {'lead': {'permissions': [
            {'action': 'shell', 'resource': 'rm *', 'effect': 'ask'}]}},
            'policies': [{'action': 'tool.use', 'resource': 'edit:private/*', 'effect': 'deny'}]}
        result = shell_wrapper_policy(old, '/Users/fixture')
        self.assertEqual(result['agents'], old['agents'])
        self.assertEqual(result['plugins'], old['plugins'])
        self.assertEqual(result['policies'][0], old['policies'][0])
        self.assertEqual(len(result['policies']), 3)
        for item in result['policies'][1:]:
            self.assertEqual(item['action'], 'integration.use')
            self.assertEqual(item['effect'], 'deny')
            self.assertNotIn('*', item['resource'])
            self.assertIn('/local-foreground-shell-guard', item['resource'])
        self.assertEqual(shell_wrapper_policy(result, '/Users/fixture'), result)

    def test_scoped_install_preserves_unrelated_config_and_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); folder = root / '.opencode'; folder.mkdir()
            target = folder / 'opencode.json'
            old = {'model': 'keep/model', 'plugins': ['keep'], 'agents': {'custom': {'system': 'keep'}}}
            target.write_text(json.dumps(old)); target.chmod(0o640)
            before = target.read_bytes()
            with patch.object(Path, 'home', return_value=root):
                self.assertEqual(installer.install(root, dry=True)['status'], 'would-update')
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(installer.install(root)['status'], 'updated')
                self.assertEqual(installer.install(root)['status'], 'same')
            result = json.loads(target.read_text())
            self.assertEqual({k: result[k] for k in old}, old)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
            self.assertEqual(set(result) - set(old), {'policies'})

    def test_jsonc_symlink_and_invalid_existing_policy_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); folder = root / '.opencode'; folder.mkdir()
            target = folder / 'opencode.jsonc'; target.write_text('// keep\n{}')
            with self.assertRaises(ValueError): installer.install(root)
            self.assertEqual(target.read_text(), '// keep\n{}')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); folder = root / '.opencode'; folder.mkdir()
            real = root / 'keep.json'; real.write_text('{}')
            (folder / 'opencode.json').symlink_to(real)
            with self.assertRaises(ValueError): installer.install(root)
        with self.assertRaises(ValueError): shell_wrapper_policy({'policies': {}}, '/Users/fixture')


if __name__ == '__main__': unittest.main()
