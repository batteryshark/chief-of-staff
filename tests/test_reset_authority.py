"""Reset startup/skill exports are file-ledger based; staging never installs roles."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render import render


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResetAuthority(unittest.TestCase):
    def test_startup_and_checkpoint_have_no_retired_authority(self):
        for path in ('kits/chief/memory/AGENTS.md', 'workflows/checkpoint/hosts/skill.md',
                     'workflows/checkpoint/hosts/opencode-command.md',
                     'kits/shared/skills/delivery-outlook.md'):
            text = render(path, '/brief')
            for stale in ('507eed6d', 'Ops alone', 'chief-ops', 'owner/Ops', 'INTERNAL OPERATIONS'):
                self.assertNotIn(stale, text, path)
        self.assertLessEqual(len(render('kits/chief/memory/AGENTS.md', '/brief').splitlines()), 12)

    def test_authority_installer_archives_and_does_not_swap_roles(self):
        module = load('install-reset-authority')
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            brief = home / '.chief-of-staff'
            brief.mkdir()
            old = '<!-- managed by chief-of-staff/install.sh -->\nOld startup\n'
            target = brief / 'AGENTS.md'
            target.write_text(old)
            module.deploy(home, brief, True)
            self.assertEqual(target.read_text(), old)
            module.deploy(home, brief)
            backup = brief / 'archive/reset-20261022-authority/installed/.chief-of-staff/AGENTS.md'
            self.assertEqual(backup.read_text(), old)
            self.assertIn('Chief memory bootstrap', target.read_text())
            self.assertFalse((home / '.config/opencode/agents').exists())

    def test_stage_has_declared_locations_and_bounded_core_plus_startup(self):
        module = load('stage-reset')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            module.stage(root / 'stage', root / 'chief', root / 'project')
            stage = root / 'stage'
            self.assertTrue((stage / 'locations.json').exists())
            chief = (stage / 'chief/.opencode/agents/chief-reset-lean-20261022.md').read_text()
            lead = (stage / 'lead/.opencode/agents/lead-reset-lean-20261022.md').read_text()
            startup = (stage / 'chief/AGENTS.md').read_text()
            self.assertLessEqual(len((chief.split('\n---\n', 1)[1] + '\n' + startup).splitlines()), 150)
            self.assertLessEqual(len(lead.split('\n---\n', 1)[1].splitlines()), 100)
            self.assertFalse((stage / 'lead/AGENTS.md').exists())
            self.assertTrue((stage / 'chief/.opencode/skills/reset-checkpoint/SKILL.md').exists())
            self.assertIn('opencode/autoinvoke: false',
                          (stage / 'chief/.opencode/skills/reset-checkpoint/SKILL.md').read_text())
            with self.assertRaises(ValueError):
                module.stage(stage, root / 'chief', root / 'project')
