"""Reset replaces split-role requirements, not their preserved historical evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from test_install import Env

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render import render
spec = importlib.util.spec_from_file_location('retire_roles', ROOT / 'scripts/retire-chief-roles.py')
retire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire)


class RetiredRolesTest(unittest.TestCase):
    def test_retired_templates_are_not_renderable(self):
        for host, suffix in (('opencode', '.md'), ('claude', '.md'), ('codex', '.config.toml')):
            for role in ('ops', 'front-door'):
                # Private historical exports are not public fixtures. Preserve
                # the same rejection/archive-retention assertion using a local
                # synthetic archived role, including an unchanged-byte check.
                with tempfile.TemporaryDirectory() as tmp:
                    archived = Path(tmp) / f'{host}-{role}{suffix}'
                    archived.write_text('Synthetic retired role; never executable.\n')
                    before = archived.read_bytes()
                    with self.assertRaises(KeyError):
                        render(f'hosts/{host}-{role}{suffix}', '/brief')
                    self.assertTrue(archived.is_file())
                    self.assertEqual(archived.read_bytes(), before)

    def test_routine_install_cannot_recreate_retired_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(Path(tmp).resolve())
            for _ in range(2):
                code, output = env.install('opencode', 'claude', 'codex')
                self.assertEqual(code, 0, output)
            for prefix, suffix in (('.config/opencode/agents', '.md'),
                                   ('.claude/agents', '.md'), ('.codex', '.config.toml')):
                for name in ('chief-ops', 'chief-front-door'):
                    self.assertFalse((env.home / prefix / (name + suffix)).exists())
                self.assertTrue((env.home / prefix / ('lead' + suffix)).exists())
                self.assertTrue((env.home / prefix / ('chief-of-staff' + suffix)).exists())

    def test_archive_and_authority_patch_preserve_transport_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            brief = home / '.chief-of-staff'
            for relative, template in [('.config/opencode/agents/chief-of-staff.md', 'hosts/opencode.md'),
                                       ('.claude/agents/chief-of-staff.md', 'hosts/claude-agent.md'),
                                       ('.claude/output-styles/chief-of-staff.md', 'hosts/claude-output-style.md'),
                                       ('.codex/chief-of-staff.config.toml', 'hosts/codex.config.toml')]:
                path = home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                text = render(template, str(brief))
                start, end, _ = retire.memory_section(text)
                path.write_text(text[:start] + '## Memory\nObsolete native ledger\n\n' + text[end:])
            old_role = home / '.config/opencode/agents/chief-ops.md'
            old_role.write_text('<!-- managed by chief-of-staff/install.sh -->\nHistorical role bytes\n')
            chief = home / '.config/opencode/agents/chief-of-staff.md'
            before = chief.read_text()
            retire.deploy(home, brief, dry=True)
            self.assertEqual(chief.read_text(), before)
            retire.deploy(home, brief)
            after = chief.read_text()
            bs, be, _ = retire.memory_section(before)
            ass, ae, _ = retire.memory_section(after)
            self.assertEqual(before[:bs], after[:ass])
            self.assertEqual(before[be:], after[ae:])
            archive = brief / 'archive/reset-20261022-retirement/installed/.config/opencode/agents'
            self.assertEqual((archive / 'chief-of-staff.md').read_text(), before)
            self.assertEqual((archive / 'chief-ops.md').read_text(),
                             '<!-- managed by chief-of-staff/install.sh -->\nHistorical role bytes\n')
            self.assertFalse(old_role.exists())
            self.assertIn('existing plain chief inbox', after)
            self.assertNotIn('Obsolete native ledger', after)
            self.assertNotIn('507eed6d', after)
