"""Offline composition and isolated-HOME install contracts; never start a server."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from hygiene_fixtures import outputs, without_hygiene
from courtesy_fixtures import existing_outputs

SRC = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('kit_render', SRC / 'scripts/render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
path_spec = importlib.util.spec_from_file_location('install_paths', SRC / 'scripts/install_paths.py')
install_paths = importlib.util.module_from_spec(path_spec)
path_spec.loader.exec_module(install_paths)


class ModularTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home),
                    'CHIEF_BRIEF_DIR': str(self.home / '.chief-of-staff'),
                    'XDG_CONFIG_HOME': str(self.root / 'config'),
                    'XDG_STATE_HOME': str(self.root / 'state'),
                    'PYTHONDONTWRITEBYTECODE': '1'}
        self.config = dict(version=1, agent='study-lead', packs=['research'],
                           owner=dict(mode='principal', style='Short plain outcome summaries.'))

    def run_install(self, *args, config=None):
        if config is not None:
            path = self.root / 'lead.json'
            path.write_text(json.dumps(config))
            args = ('--lead-config', str(path), *args)
        return subprocess.run(['bash', str(SRC / 'install.sh'), *args], env=self.env,
                              capture_output=True, text=True, timeout=120)

    def test_default_parity_against_original_installer_all_managed_outputs(self):
        # Original bytes, not a reconstructed expected prompt. No checkout/reset.
        old = self.root / 'baseline'
        old.mkdir()
        files = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'ac83f44'],
                               cwd=SRC, capture_output=True, text=True, check=True, timeout=20).stdout.splitlines()
        prefixes = ('hosts/', 'workflows/', 'chief-home/')
        for name in files:
            if name in ('install.sh', 'prompt.md', 'lead.md', 'models.md',
                        'scripts/chief-openchamber', 'scripts/chief-portfolio') or name.startswith(prefixes):
                data = subprocess.run(['git', 'show', f'ac83f44:{name}'], cwd=SRC,
                                      capture_output=True, check=True, timeout=20).stdout
                path = old / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        before = subprocess.run(['bash', str(old / 'install.sh'), '--print'], env=self.env,
                                capture_output=True, text=True, check=True, timeout=120).stdout
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        # Only exact hash-pinned insertions at six named output positions may differ.
        # The pre-existing ac83f44 guard still checks every other byte/older addition.
        normalized = without_hygiene(existing_outputs(outputs(result.stdout, SRC, self.home)))
        after = ''.join('=== ' + path + '\n' + text for path, text in normalized.items())
        after = after.replace('<HOME>', str(self.home)).replace('<SOURCE>', str(SRC))
        for addition in (render.LEVELS, render.OWNER_SAFETY, render.read('kits/shared/docket.md'),
                         render.read('kits/shared/fleet.md'), render.read('services/directory/instructions.md')):
            after = after.replace('\n\n' + addition, '')
        # Added after the split: sessions stay in the project folder (OpenChamber 2.4.0 worktree moves).
        _, marker, rule = json.loads(render.read('practices/engineering/lead.json'))['WORKSPACE'].partition('\n- Sessions stay')
        self.assertTrue(marker)
        after = after.replace(marker + rule, '')
        self.assertEqual(before.replace(str(old), '<SOURCE>'), after.replace(str(SRC), '<SOURCE>'))
        self.assertEqual(result.stdout.count('=== '), 22)

    def test_default_install_and_reinstall_preserve_seeds_and_bindings(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        home = self.home / '.chief-of-staff'
        (home / 'principal.md').write_text('private fixture\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual((home / 'principal.md').read_text(), 'private fixture\n')
        shape = (self.home / '.config/opencode/commands/shape.md').read_text()
        checkpoint = (self.home / '.config/opencode/commands/checkpoint.md').read_text()
        self.assertIn('agent: chief-of-staff', shape)
        self.assertIn('agent `chief-of-staff`', checkpoint)
        lead = (self.home / '.config/opencode/agents/lead.md').read_text()
        self.assertIn(str(home / 'chief.json'), lead)
        self.assertIn('returnResult: true', lead)

    def test_authorized_levels_and_docket_reach_both_prompts(self):
        result = self.run_install('--print', 'opencode')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('## Shared services: Docket'), 2)
        self.assertEqual(result.stdout.count('L1 principal'), 2)
        self.assertIn("Docket checkout's `AGENT_USAGE.md`", result.stdout)
        self.assertIn('do not add a sleep/poll loop', result.stdout)
        self.assertEqual(result.stdout.count('## Shared services: Fleet'), 2)
        for phrase in ('fleet add', 'fleet adopt', 'health probe and group',
                       "Fleet checkout's `README.md`", '~/.config/fleet/services.json',
                        "Check the operator's existing registry", 'avoid duplicate',
                        'no permission to probe, start or install services'):
            self.assertIn(phrase, result.stdout)

    def test_each_pack_is_real_and_attachable(self):
        checks = {'engineering': ('git worktree', 'parent before the child', 'tests, evidence'),
                  'research': ('source ledger', 'Cite claims', 'conflicting evidence')}
        for pack, expected in checks.items():
            with self.subTest(pack=pack):
                config = {**self.config, 'packs': [pack]}
                result = self.run_install('--print', 'opencode', config=config)
                self.assertEqual(result.returncode, 0, result.stderr)
                for phrase in expected:
                    self.assertIn(phrase, result.stdout)
                self.assertNotIn('{{', result.stdout)

    def test_packs_can_be_combined(self):
        result = self.run_install('--print', 'claude', config={**self.config,
                                  'packs': ['engineering', 'research']})
        self.assertEqual(result.returncode, 0, result.stderr)
        for phrase in ('git worktree', 'source ledger'):
            self.assertIn(phrase, result.stdout)

    def test_principal_standalone_install_all_hosts_without_chief(self):
        result = self.run_install(config=self.config)
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = list(self.home.rglob('*'))
        self.assertEqual(sum(p.is_file() for p in paths), 12)  # nine outputs + three exact private receipts
        from courtesy_owned import OwnedSkills, digest
        from courtesy import target as courtesy_target
        receipts = {OwnedSkills(self.home, {}).record_path(courtesy_target(self.home, h))
                    for h in ('opencode', 'claude', 'codex')}
        for receipt in receipts:
            data = json.loads(receipt.read_text())
            self.assertEqual(data['owner'], 'standalone:study-lead')
            self.assertEqual(data['sha256'], digest((self.home / data['path']).read_bytes()))
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        for path in paths:
            if path.is_file() and path not in receipts:
                text = path.read_text()
                self.assertNotIn('.chief-of-staff', text)
                self.assertNotIn('chief.json', text)
                self.assertNotIn('technical chief', text)
                self.assertNotIn('{{', text)
        lead = (self.home / '.config/opencode/agents/study-lead.md').read_text()
        self.assertIn('Short plain outcome summaries.', lead)
        self.assertIn('outcomes, not mechanics', lead)
        self.assertIn('No chief memory is required', lead)
        self.assertFalse((self.home / '.chief-of-staff').exists())
        self.assertEqual(self.run_install(config=self.config).returncode, 0)
        self.assertEqual(self.run_install('--uninstall', config=self.config).returncode, 0)
        self.assertFalse(any(p.is_file() for p in self.home.rglob('*')))

    def test_agent_owner_uses_explicit_live_pointer_and_fallback(self):
        config = {**self.config, 'owner': dict(mode='agent', pointer=str(self.root / 'owner.json'), label='research coordinator')}
        result = self.run_install('--print', 'opencode', config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.root / 'owner.json'), result.stdout)
        self.assertIn('every send', result.stdout)
        self.assertIn('`session` and `directory`', result.stdout)
        self.assertIn('never guess, title-search', result.stdout)
        self.assertIn('returnResult: true', result.stdout)
        self.assertNotIn('.chief-of-staff', result.stdout)

    def test_config_errors_fail_before_writes(self):
        invalid = [None, {}, {**self.config, 'owner': {}},
                   {**self.config, 'owner': dict(mode='principal')},
                   {**self.config, 'owner': dict(mode='agent', pointer='relative', label='chief')},
                   {**self.config, 'owner': dict(mode='webhook', url='https://invalid')},
                   {**self.config, 'packs': ['missing']}, {**self.config, 'packs': ['life-admin']},
                   {**self.config, 'packs': []},
                   {**self.config, 'packs': ['research', 'research']},
                   {**self.config, 'agent': '../escape'}, {**self.config, 'agent': 'lead'},
                   {**self.config, 'extra': True}, {**self.config, 'version': True}]
        for config in invalid:
            path = self.root / 'invalid.json'
            path.write_text(json.dumps(config))
            result = self.run_install('--lead-config', str(path))
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(list(self.home.iterdir()), [])
        result = self.run_install('--lead-config', str(self.root / 'absent.json'))
        self.assertNotEqual(result.returncode, 0)

    def test_standalone_does_not_overwrite_unowned_or_symlink_targets(self):
        path = self.home / '.config/opencode/agents/study-lead.md'
        path.parent.mkdir(parents=True)
        path.write_text('user work')
        self.assertNotEqual(self.run_install(config=self.config).returncode, 0)
        self.assertEqual(path.read_text(), 'user work')
        self.assertFalse((self.home / '.claude').exists())
        path.unlink()
        path.symlink_to(self.root / 'missing')
        self.assertNotEqual(self.run_install(config=self.config).returncode, 0)
        self.assertTrue(path.is_symlink())

    def test_lead_owned_sources_and_no_colliding_root(self):
        # Accepted closeout moved the owned goal log to ROOT LEAD.md after the
        # canonical prompt was extracted. Check the prompt location, not absence
        # of a legitimate (case-insensitive) root log.
        root_log = SRC / 'LEAD.md'
        if root_log.exists():
            self.assertIn('lead log', root_log.read_text().splitlines()[0])
        for name in ('core.md', 'log.template.md', 'skills/checkpoint.md', 'skills/checkpoint-technical.md'):
            self.assertTrue((SRC / 'kits/lead' / name).is_file())
        core = (SRC / 'kits/lead/core.md').read_text()
        for phrase in ('git worktree', 'merge order', 'chief.json', '.chief-of-staff', 'tests, evidence'):
            self.assertNotIn(phrase, core)
        self.assertIn('owns one outcome', render.LEVELS)
        with self.assertRaises(KeyError):
            render.expand('{{MISSING}}', {})
        with self.assertRaises(KeyError):
            render.render('invented-lead-template.md', str(self.home))

    def test_invalid_technical_profile_fails_closed(self):
        for value in ({}, {'version': 2}, None):
            with patch.object(render, 'read', return_value=json.dumps(value)):
                with self.assertRaises(ValueError):
                    render.technical_values(str(self.home))

    def standalone_paths(self, home=None):
        home = home or self.home
        return [home / path for path in (
            '.config/opencode/agents/study-lead.md',
            '.config/opencode/commands/study-lead-checkpoint.md',
            '.claude/agents/study-lead.md',
            '.claude/skills/study-lead-checkpoint/SKILL.md',
            '.codex/study-lead.config.toml',
            '.codex/skills/study-lead-checkpoint/SKILL.md')]

    def assert_checkpoint_bindings(self, home=None):
        paths = self.standalone_paths(home)
        for agent, checkpoint in zip(paths[::2], paths[1::2]):
            text = agent.read_text()
            self.assertIn('Run the `study-lead-checkpoint` skill', text)
            self.assertNotIn('Run the `checkpoint` skill', text)
            adapter = checkpoint.read_text()
            self.assertIn('resource is `study-lead-checkpoint`', adapter)
            self.assertIn('agent `study-lead`', adapter)
            self.assertIn('continuing lead uses `study-lead-checkpoint`', adapter)
            self.assertNotIn('chief.json', adapter)
            self.assertNotIn('{{', adapter)
            if checkpoint.suffix == '.md' and checkpoint.name == 'SKILL.md':
                self.assertIn('name: study-lead-checkpoint\n', adapter)
            else:
                self.assertIn('agent: study-lead\n', adapter)

    def test_checkpoint_binding_coexists_with_defaults_all_hosts(self):
        result = self.run_install('opencode', 'claude', 'codex')
        self.assertEqual(result.returncode, 0, result.stderr)
        defaults = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertIn('Run the `checkpoint` skill',
                      (self.home / '.config/opencode/agents/lead.md').read_text())
        result = self.run_install(config=self.config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_checkpoint_bindings()
        for path, original in defaults.items():
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.run_install('--uninstall', config=self.config).returncode, 0)
        self.assertEqual(defaults, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_standalone_checkpoint_is_physically_independent_of_chief_sources(self):
        detached = self.root / 'independent-source'
        detached.mkdir()
        for name in ('install.sh', 'scripts/render.py', 'scripts/install-lead.py',
                     'scripts/install_paths.py', 'scripts/courtesy.py', 'scripts/courtesy_owned.py',
                     'kits/shared/docket.md', 'kits/shared/fleet.md'):
            target = detached / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SRC / name, target)
        for name in ('kits/lead', 'practices/research', 'practices/upstream-courtesy'):
            shutil.copytree(SRC / name, detached / name)
        for name in ('kits/chief', 'profiles', 'hosts', 'workflows', 'routing', 'runway'):
            self.assertFalse((detached / name).exists())
        config_path = self.root / 'independent.json'
        for owner in (self.config['owner'], dict(mode='agent', pointer=str(self.root / 'owner.json'), label='coordinator')):
            config_path.write_text(json.dumps({**self.config, 'owner': owner}))
            result = subprocess.run(['bash', str(detached / 'install.sh'), '--lead-config', str(config_path)],
                                    env=self.env, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_checkpoint_bindings()
            self.assertEqual(sum(p.is_file() for p in self.home.rglob('*')), 12)
            self.assertFalse((self.home / '.chief-of-staff').exists())

    def test_linked_destination_parents_refused_in_every_mode(self):
        for relative in ('.config/opencode', '.claude/skills', '.codex/skills/study-lead-checkpoint'):
            with self.subTest(relative=relative):
                case = self.root / ('case-' + relative.replace('/', '-'))
                home = case / 'home'
                home.mkdir(parents=True)
                outside = case / 'outside'
                outside.mkdir()
                sentinel = outside / 'keep.txt'
                sentinel.write_text('untouched')
                linked = home / relative
                linked.parent.mkdir(parents=True, exist_ok=True)
                linked.symlink_to(outside, target_is_directory=True)
                self.env['HOME'] = str(home)
                for args in ((), ('--uninstall',), ('--print',), ('--dry-run',)):
                    result = self.run_install(*args, config=self.config)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('symlinked destination', result.stderr)
                    self.assertEqual(list(outside.iterdir()), [sentinel])
                    self.assertEqual(sentinel.read_text(), 'untouched')
                    self.assertFalse(any(p.is_file() for p in home.rglob('*')))

    def test_last_linked_target_blocks_all_earlier_updates_and_removals(self):
        self.assertEqual(self.run_install(config=self.config).returncode, 0)
        paths = self.standalone_paths()
        # Make the first owned output differ, so install would otherwise update it.
        paths[0].write_text(paths[0].read_text() + '\nretained fixture text\n')
        linked = paths[-1].parent
        outside = self.root / 'linked-last-skill'
        linked.rename(outside)
        linked.symlink_to(outside, target_is_directory=True)
        before = {p: p.read_bytes() for p in paths}
        for args in ((), ('--uninstall',), ('--print',), ('--dry-run',)):
            result = self.run_install(*args, config=self.config)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('symlinked destination', result.stderr)
            self.assertTrue(linked.is_symlink())
            self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_last_unowned_leaf_and_link_conflicts_preserve_earlier_files(self):
        self.assertEqual(self.run_install(config=self.config).returncode, 0)
        paths = self.standalone_paths()
        last = paths[-1]
        last.write_text('unowned fixture')
        before = {p: p.read_bytes() for p in paths}
        for args in ((), ('--uninstall',)):
            result = self.run_install(*args, config=self.config)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('not owned', result.stderr)
            self.assertEqual(before, {p: p.read_bytes() for p in paths})
        last.unlink()
        last.symlink_to(self.root / 'absent-leaf')
        for args in ((), ('--uninstall',)):
            result = self.run_install(*args, config=self.config)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(last.is_symlink())
            self.assertFalse(last.exists())
            self.assertEqual({p: before[p] for p in paths[:-1]}, {p: p.read_bytes() for p in paths[:-1]})

    def test_selected_home_alias_and_external_ancestor_alias_are_allowed(self):
        root_alias = self.root / 'home-alias'
        root_alias.symlink_to(self.home, target_is_directory=True)
        ancestor_alias = self.root / 'ancestor-alias'
        ancestor_alias.symlink_to(self.root, target_is_directory=True)
        for selected in (root_alias, ancestor_alias / 'home'):
            self.env['HOME'] = str(selected)
            result = self.run_install(config=self.config)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_checkpoint_bindings()
            self.assertEqual(self.run_install('--uninstall', config=self.config).returncode, 0)
            self.assertFalse(any(p.is_file() for p in self.home.rglob('*')))

    def test_destination_helper_rejects_escapes_links_and_nondirectory_parents(self):
        root = install_paths.DestinationRoot(self.home)
        for target in (self.root / 'outside/file', self.home / '../escape', self.home):
            with self.assertRaises(ValueError):
                root.validate_all([target])
        (self.home / 'real').mkdir()
        (self.home / 'internal-link').symlink_to(self.home / 'real', target_is_directory=True)
        (self.home / 'dangling-link').symlink_to(self.root / 'absent', target_is_directory=True)
        (self.home / 'file-parent').write_text('not a directory')
        for name in ('internal-link', 'dangling-link', 'file-parent'):
            with self.assertRaises(ValueError):
                root.validate_all([self.home / name / 'file'])
        root.validate_all([self.home / 'real/new-file', self.home / 'new-parent/file'])


if __name__ == '__main__':
    unittest.main()
