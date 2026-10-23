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
        self.assertIn('\n# Chief\n', chief)
        self.assertIn('reset-worker-dispatch', chief)
        worker = self.e.home / '.config/opencode/skills/reset-worker-dispatch/SKILL.md'
        self.assertIn('whole approved goal/handover, lead agent', worker.read_text())

    def test_visual_preview_guidance_renders_for_chief_and_lead(self):
        code, out = self.e.install('opencode', 'claude', 'codex')
        self.assertEqual(code, 0, out)
        for path in ('.config/opencode/agents/chief-of-staff.md',
                     '.claude/agents/chief-of-staff.md',
                     '.claude/output-styles/chief-of-staff.md',
                     '.codex/chief-of-staff.config.toml'):
            text = (self.e.home / path).read_text()
            # The accepted lean core replaces preview-copy choreography with
            # outcome/voice guidance; native file edit boundaries stay intact.
            self.assertIn('phone-usable results for visual/taste review', text, path)
            self.assertIn('silent detail', text, path)
        for path in ('.config/opencode/agents/lead.md', '.claude/agents/lead.md',
                     '.codex/lead.config.toml'):
            self.assertIn('reset-worker-dispatch', (self.e.home / path).read_text(), path)
        worker = self.e.home / '.config/opencode/skills/reset-worker-dispatch/SKILL.md'
        self.assertIn('headless/offscreen', worker.read_text())

    def test_stop_conditions_reach_chief_and_lead(self):
        code, out = self.e.install('claude')
        self.assertEqual(code, 0, out)
        chief = (self.e.home / '.claude/agents/chief-of-staff.md').read_text()
        self.assertIn('After the principal rejects the same thing twice', chief)
        self.assertIn('No restart until their decision', chief)
        lead = (self.e.home / '.claude/agents/lead.md').read_text()
        for section in ('STOP project work', 'No resume before their decision', 'failed approaches'):
            self.assertIn(section, lead)

    def test_uninstall_removes_lead_agents(self):
        self.e.install('opencode', 'claude', 'codex')
        code, out = self.e.install('--uninstall', 'opencode', 'claude', 'codex')
        self.assertEqual(code, 0, out)
        self.assertFalse((self.e.home / '.claude/agents/lead.md').exists())

    def test_inbox_dirs_preserve_existing_entries_and_personal_state(self):
        code, out = self.e.install('home')
        self.assertEqual(code, 0, out)
        self.assertTrue((self.e.brief / 'archive/inbox').is_dir())
        keep = {self.e.brief / name: content for name, content in (
            ('inbox/fixture.md', 'unprocessed fixture'),
            ('archive/inbox/old.md', 'processed fixture'),
            ('open.md', 'concurrent open items'), ('principal.md', 'personal'),
            ('brief.md', 'personal brief'))}
        for path, content in keep.items():
            path.write_text(content)
        code, out = self.e.install('home')
        self.assertEqual(code, 0, out)
        for path, content in keep.items():
            self.assertEqual(path.read_text(), content)


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
        # Legacy fallback text is not authenticated current status or a principal
        # ask. The accepted portfolio behavior flags clarification, not raw replay.
        self.assertNotIn('Lantern status line.', out)
        self.assertNotIn('Lantern question.', out)
        self.assertIn('Agent-owned: lead to clarify', out)
        self.assertIn('Gone · no lead · LEAD fallback · log updated unknown/missing', out)


if __name__ == '__main__':
    unittest.main()
