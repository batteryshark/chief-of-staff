"""install.sh renders the lead agents, and chief-portfolio reads the leads' logs.

Every run uses a temporary HOME and brief directory, so nothing outside them is touched.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent


class Env:
    def __init__(self, root):
        self.home = Path(root) / 'home'
        self.brief = Path(root) / 'brief'
        self.home.mkdir()
        self.env = {'HOME': str(self.home), 'CHIEF_BRIEF_DIR': str(self.brief),
                    'PATH': os.pathsep.join([os.path.dirname(sys.executable), '/usr/bin', '/bin'])}

    def install(self, *args):
        out = subprocess.run([str(SRC / 'install.sh'), *args], env=self.env, capture_output=True,
                             text=True, timeout=120)
        return out.returncode, out.stdout + out.stderr


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.e = Env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_installs_lead_agents_from_the_lead_prompt(self):
        code, out = self.e.install('opencode', 'claude', 'codex')
        self.assertEqual(code, 0, out)
        for path in ('.config/opencode/agents/lead.md', '.claude/agents/lead.md', '.codex/lead.config.toml'):
            text = (self.e.home / path).read_text()
            self.assertIn('\n# Lead\n', text, path)
            self.assertIn('LEAD.md', text, path)
        self.assertIn('name: lead\n', (self.e.home / '.claude/agents/lead.md').read_text())
        chief = (self.e.home / '.config/opencode/agents/chief-of-staff.md').read_text()
        self.assertIn('\n# Chief of staff\n', chief)
        self.assertIn('agent: "lead"', chief)
        self.assertIn('[lead] <Project>', chief)

    def test_stop_conditions_reach_chief_and_lead(self):
        code, out = self.e.install('claude')
        self.assertEqual(code, 0, out)
        chief = (self.e.home / '.claude/agents/chief-of-staff.md').read_text()
        self.assertIn('**Stop conditions.**', chief)
        self.assertIn('**Continue or shelve.**', chief)
        lead = (self.e.home / '.claude/agents/lead.md').read_text()
        for section in ('## Stop conditions', "## Attempts that didn't work", 'First step on resume'):
            self.assertIn(section, lead)

    def test_uninstall_removes_lead_agents(self):
        self.e.install('opencode', 'claude', 'codex')
        code, out = self.e.install('--uninstall', 'opencode', 'claude', 'codex')
        self.assertEqual(code, 0, out)
        self.assertFalse((self.e.home / '.claude/agents/lead.md').exists())


class PortfolioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.e = Env(self.tmp.name)
        self.root = Path(self.tmp.name)
        code, out = self.e.install('bin')
        self.assertEqual(code, 0, out)
        # Without it, chief-portfolio reports every session as unknown instead of asking OpenChamber.
        (self.e.home / '.local/bin/chief-openchamber').unlink()

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, name):
        folder = self.root / name
        folder.mkdir()
        (folder / 'LEAD.md').write_text(
            f'# {name}: lead log\n\nLead session ses_{name}1 · chief: see chief.json\n\n'
            f'## Status\n{name} status line.\n\n## Waiting on the principal\n- 2026-10-14: {name} question.\n')
        return folder

    def portfolio(self, brief):
        self.e.brief.mkdir(exist_ok=True)
        (self.e.brief / 'brief.md').write_text(brief)
        out = subprocess.run([sys.executable, str(self.e.home / '.local/bin/chief-portfolio')], env=self.e.env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_reads_each_lead_log_once(self):
        orchard = self.project('Orchard')
        lantern = self.project('Lantern')
        out = self.portfolio(f'| Orchard | {orchard}/LEAD.md |\n| Lantern | {lantern}/LEAD.md |\n'
                             f'{lantern}/LEAD.md\n| Gone | {self.root}/Gone/LEAD.md |\n')
        self.assertIn('Orchard · lead unknown', out)
        self.assertEqual(out.count('Lantern · lead unknown'), 1, out)
        self.assertIn('Lantern status line.', out)
        self.assertIn('Lantern question.', out)
        self.assertIn('Gone/LEAD.md: log missing', out)


if __name__ == '__main__':
    unittest.main()
