"""Guidance/render/install tests only. No live adoption or worktree operations."""
import json
from pathlib import Path
import unittest

from hygiene_fixtures import outputs, pinned_print, without_hygiene
from courtesy_fixtures import existing_outputs
import test_modular as modular
import test_profiles as profiles

render, SRC = modular.render, modular.SRC


class WorktreeHygieneTests(unittest.TestCase):
    setUp = modular.ModularTests.setUp
    run_install = modular.ModularTests.run_install

    def test_exact_authorized_delta_all_19_outputs_and_6623_guard(self):
        old = self.root / 'old'
        prior = self.root / 'prior'
        base = outputs(pinned_print('81e3458', old, self.env), old, self.home)
        accepted = outputs(pinned_print('6623f0f', prior, self.env), prior, self.home)
        self.assertEqual(base, accepted)  # Preserve the desk-disabled prechange guard.
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        now = existing_outputs(outputs(result.stdout, SRC, self.home))
        self.assertEqual(len(now), 19)
        self.assertEqual(without_hygiene(now), base)
        changed = {path for path in now if now[path] != base[path]}
        gold = json.loads((SRC / 'tests/hygiene-default-insertions.json').read_text())
        self.assertEqual(changed, set(gold))
        self.assertEqual(len(changed), 6)
        # A mutation inside an approved insertion cannot hide under normalization.
        path = next(iter(gold))
        corrupted = dict(now)
        start = gold[path][0][0]
        corrupted[path] = now[path][:start] + '!' + now[path][start + 1:]
        with self.assertRaises(AssertionError):
            without_hygiene(corrupted)

    def assert_core(self, text):
        for phrase in ('## Worktree hygiene', '**8 registered secondary worktrees per repository**',
                       'ALL branches and owners', 'main checkout does not count',
                       'same step', 'Keep the branch', 'EVERY checkpoint, park, goal completion and handover',
                       'EACH retained', 'Kept worktrees', 'BEFORE creating a ninth',
                       'trigger an immediate safe sweep', 'create no', 'serialize or pause',
                       'unknown ownership', 'every active session', 'N/A', 'without moving sessions'):
            self.assertIn(phrase, text)

    def test_default_installed_wrappers_and_checkpoint_all_hosts(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in ('.config/opencode/agents/lead.md', '.claude/agents/lead.md', '.codex/lead.config.toml'):
            text = (self.home / path).read_text()
            self.assert_core(text)
            for phrase in ('--untracked-files=all --ignored', 'no --force', 'no branch deletion',
                           'submodules, locks', 'no unlocking', 'unknown metadata', 'preserve\n  a branch ref'):
                self.assertIn(phrase, text)
        for path in ('.config/opencode/commands/checkpoint.md', '.claude/skills/checkpoint/SKILL.md',
                     '.codex/skills/checkpoint/SKILL.md'):
            text = (self.home / path).read_text()
            for phrase in ('EVERY checkpoint, park, goal completion and before handover',
                           'EACH retained', 'count / 8', 'Non-git projects record N/A'):
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
            text = render.render('hosts/' + host, home, desk_project='fixture')
            self.assert_core(text)
            self.assertIn('No desk-originated Goal:', text)
        for host in ('opencode-command.md', 'skill.md', 'codex-openai.yaml'):
            text = render.render('workflows/checkpoint/hosts/' + host, home, desk_project='fixture')
            if host == 'codex-openai.yaml':
                continue  # Host metadata only; contains no workflow body.
            for phrase in ('EVERY checkpoint, park and goal completion', 'EACH retained worktree',
                           'above 8, sweep immediately', 'trusted registry', 'keeping branches'):
                self.assertIn(phrase, text)
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
