"""Guidance/render/install tests only. No live adoption or worktree operations."""
from pathlib import Path
import unittest

from hygiene_fixtures import outputs
from effective_roles import effective, assert_current_exports
import test_modular as modular
import test_profiles as profiles

render, SRC = modular.render, modular.SRC


class WorktreeHygieneTests(unittest.TestCase):
    setUp = modular.ModularTests.setUp
    run_install = modular.ModularTests.run_install

    def test_approved_lean_exports_preserve_worktree_safety_and_mutation_guard(self):
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        now = outputs(result.stdout, SRC, self.home)
        assert_current_exports(self, now, SRC, self.home, self.home / '.chief-of-staff')
        path = '<HOME>/.config/opencode/skills/reset-worktree-safety/SKILL.md'
        self.assert_core(now[path])
        corrupted = dict(now)
        corrupted[path] = now[path].replace('No force', 'Force is allowed')
        with self.assertRaises(AssertionError):
            assert_current_exports(self, corrupted, SRC, self.home, self.home / '.chief-of-staff')

    def assert_core(self, text):
        if '# Clean-only worktree lifecycle' not in text:
            # Standalone/scoped profiles retain the established non-lean composition.
            for phrase in ('## Worktree hygiene', '**8 registered secondary worktrees per repository**',
                           'ALL branches and owners', 'main checkout does not count', 'same step',
                           'Keep the branch', 'EVERY checkpoint, park, goal completion and handover',
                           'EACH retained', 'Kept worktrees', 'BEFORE creating a ninth',
                           'trigger an immediate safe sweep', 'create no', 'serialize or pause',
                           'unknown ownership', 'every active session', 'N/A', 'without moving sessions'):
                self.assertIn(phrase, text)
            return
        for phrase in ('eight secondary worktrees across all owners, main excluded',
                       'At eight, safely clean', 'above eight, sweep now', 'serialize/pause',
                       'Keep the branch', 'same step', 'pending tools/effects; unknown is protected',
                       'Never strand a session or remove any active cwd', 'main, other owners, live workers, locked trees',
                       '--untracked-files=all --ignored', 'without following links', 'No force',
                       'branch deletion', 'unlocking or pruning of unknown metadata', 'N/A',
                       'Inspect submodules and locks',
                       'sessions stay at project root unless the principal asks'):
            self.assertIn(phrase, text)

    def test_default_installed_wrappers_and_checkpoint_all_hosts(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in ('.config/opencode/agents/lead.md', '.claude/agents/lead.md', '.codex/lead.config.toml'):
            text = (self.home / path).read_text()
            self.assertIn('reset-worktree-safety', text)
            procedure = (self.home / ('.config/opencode/skills/reset-worktree-safety/SKILL.md' if path.startswith('.config')
                                      else '.local/share/chief-of-staff/reset/reset-worktree-safety.md')).read_text()
            self.assert_core(procedure)
            self.assertIn('Preserve a branch ref for detached abandoned commits', procedure)
        for path in ('.config/opencode/commands/checkpoint.md', '.claude/skills/checkpoint/SKILL.md',
                     '.codex/skills/checkpoint/SKILL.md'):
            text = (self.home / path).read_text()
            for phrase in ('reset-worktree-safety', 'branches preserved', 'Retain and record uncertainty'):
                self.assertIn(phrase, text)

    def test_standalone_all_practices_and_claude_modular_host(self):
        for pack in ('engineering', 'research'):
            config = {**self.config, 'packs': [pack]}
            result = self.run_install(config=config)
            self.assertEqual(result.returncode, 0, result.stderr)
            for path in modular.ModularTests.standalone_paths(self):
                text = path.read_text()
                if 'agents/' in str(path) or path.suffix == '.toml':
                    self.assert_core(text)
                else:
                    for phrase in ('EACH retained', 'count / 8', 'N/A', 'Never force'):
                        self.assertIn(phrase, text)
                self.assertNotIn('{{', text)
            # Non-git practices receive the conditional core, not git commands.
            if pack != 'engineering':
                self.assertNotIn('git -C', (self.home / '.claude/agents/study-lead.md').read_text())

    def test_desk_optin_hosts_and_checkpoint_supplement_source_only(self):
        home = str(self.home)
        for host in ('opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml'):
            with self.assertRaisesRegex(ValueError, 'retired'):
                render.render('hosts/' + host, home, desk_project='fixture')
        for host in ('opencode-command.md', 'skill.md', 'codex-openai.yaml'):
            with self.assertRaisesRegex(ValueError, 'retired'):
                render.render('workflows/checkpoint/hosts/' + host, home, desk_project='fixture')
        self.assertFalse((self.home / '.chief-of-staff').exists())


class ScopedWorktreeHygieneTests(unittest.TestCase):
    setUp = profiles.ProfileTests.setUp
    run_install = profiles.ProfileTests.run_install

    def test_scoped_installed_core_and_both_checkpoint_surfaces(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        WorktreeHygieneTests.assert_core(self, (self.domain / '.opencode/agents/example-lead.md').read_text())
        for path in ('commands/example-checkpoint.md', 'skills/example-checkpoint/SKILL.md'):
            text = (self.domain / '.opencode' / path).read_text()
            for phrase in ('EACH retained', 'count / 8', 'N/A', 'domain_lead_start'):
                self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
