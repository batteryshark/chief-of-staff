"""Isolated stdlib packaging checks. Fake transport is hashed, never imported."""
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parent.parent
GUIDES = ('README.md', 'models/README.md', 'runway/README.md', 'docket/README.md',
          'fleet/README.md', 'voicestack/README.md', 'directory/README.md')


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='packaging-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.package = self.root / 'relocated-package'
        shutil.copytree(SRC, self.package, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.home),
                    'TMPDIR': str(self.root), 'PYTHONDONTWRITEBYTECODE': '1',
                    **{f'XDG_{k}_HOME': str(self.home / k.lower()) for k in ('CONFIG', 'DATA', 'STATE', 'CACHE')}}
        self.transport = self.root / 'transport/src/plugin.js'
        self.transport.parent.mkdir(parents=True)
        self.transport.write_text('// Synthetic fixture; never loaded.\nexport default {};\n')
        self.env['CHIEF_A2A_MODULE'] = str(self.transport)
        self.domain = self.home / '.chiefs/example'

    def run_install(self, *args):
        return subprocess.run(['/bin/bash', str(self.package / 'install.sh'), *args],
                              cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10)

    def scoped(self, *args):
        return self.run_install('--profile', 'example', *args)

    def install_scope(self):
        result = self.scoped()
        self.assertEqual(result.returncode, 0, result.stderr)

    def snapshot(self):
        return {str(p.relative_to(self.home)): ('link', str(p.readlink())) if p.is_symlink()
                else ('file', hashlib.sha256(p.read_bytes()).hexdigest())
                for p in self.home.rglob('*') if p.is_symlink() or p.is_file()}

    def assert_blocked_unchanged(self, call):
        before = self.snapshot()
        result = call()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(before, self.snapshot(), result.stderr)

    def test_transport_selection_pin_and_validation_in_all_modes(self):
        for args in (('--print',), ('--dry-run',), ()):
            for bad in ('relative.js', str(self.root / 'missing.js'), ''):
                self.env['CHIEF_A2A_MODULE'] = bad
                self.assert_blocked_unchanged(lambda: self.scoped(*args))
        self.env['CHIEF_A2A_MODULE'] = str(self.transport)
        self.env['CHIEF_A2A_ROOT'] = str(self.root / 'wrong')
        self.assert_blocked_unchanged(lambda: self.scoped('--print'))
        self.env['CHIEF_A2A_ROOT'] = str(self.transport.parent.parent)
        for args in (('--print',), ('--dry-run',)):
            before = self.snapshot()
            result = self.scoped(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, self.snapshot())
        self.install_scope()
        plugin = (self.domain / '.opencode/plugins/chief-domain/index.ts').read_text()
        config = json.loads(re.search(r'makePlugin\((.*)\);', plugin)[1])
        self.assertEqual(config['transport_module'], self.transport.as_uri())
        self.assertEqual(config['transport_sha256'], hashlib.sha256(self.transport.read_bytes()).hexdigest())
        self.assertIn((self.package / 'hosts/domain-policy/index.mjs').as_uri(), plugin)
        self.assertNotIn(str(SRC), plugin.replace(str(self.root), '<fixture>'))

    def test_transport_absent_uninstall_retains_seeds_and_other_owner(self):
        self.install_scope()
        inventory = json.loads((self.domain / '.kit-install.json').read_text())
        seed = self.domain / 'principal.md'
        seed.write_text('private fixture retained\n')
        self.transport.unlink()
        self.env.pop('CHIEF_A2A_MODULE')
        self.env['CHIEF_A2A_ROOT'] = '/missing/ignored'
        result = self.scoped('--uninstall')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in inventory['owned']:
            self.assertFalse((self.home / name).exists())
        self.assertEqual(seed.read_text(), 'private fixture retained\n')
        registry = json.loads((self.home / '.config/chief-of-staff/domains.json').read_text())
        self.assertEqual([r['id'] for r in registry['domains']], ['technical'])

    def test_modified_unowned_and_courtesy_refuse_without_mutation(self):
        self.install_scope()
        self.transport.unlink()
        for rel in ('AGENTS.md', '.kit-resources/services/README.md',
                    '.opencode/skills/upstream-courtesy/SKILL.md'):
            target = self.domain / rel
            original = target.read_text()
            for text in (original + '\nmodified fixture', 'unowned fixture'):
                target.write_text(text)
                self.assert_blocked_unchanged(lambda: self.scoped('--uninstall'))
            target.write_text(original)
        # Updates also refuse changed guides, even when their marker survives.
        self.transport.write_text('// synthetic fixture\n')
        target = self.domain / '.kit-resources/services/README.md'
        target.write_text(target.read_text() + '\nmodified fixture')
        self.assert_blocked_unchanged(self.scoped)

    def test_leaf_ancestor_links_and_inventory_cannot_extend_authority(self):
        self.install_scope()
        self.transport.unlink()
        target = self.domain / 'AGENTS.md'
        outside = self.root / 'saved.md'
        target.rename(outside)
        target.symlink_to(outside)
        self.assert_blocked_unchanged(lambda: self.scoped('--uninstall'))
        target.unlink()
        outside.rename(target)
        ancestor = self.domain / '.kit-resources'
        moved = self.root / 'saved-resources'
        ancestor.rename(moved)
        ancestor.symlink_to(moved, target_is_directory=True)
        self.assert_blocked_unchanged(lambda: self.scoped('--uninstall'))
        ancestor.unlink()
        moved.rename(ancestor)
        inventory = self.domain / '.kit-install.json'
        original = json.loads(inventory.read_text())
        for mutation in ('path', 'hash', 'identity', 'seeds', 'version'):
            data = json.loads(json.dumps(original))
            if mutation == 'path': data['owned']['unowned.md'] = '0' * 64
            elif mutation == 'hash': data['owned'][next(iter(data['owned']))] = 'unchecked'
            elif mutation == 'identity': data['identity']['id'] = 'other'
            elif mutation == 'seeds': data['private_seeds'] = ['unowned.md']
            else: data['version'] = True
            inventory.write_text(json.dumps(data))
            self.assert_blocked_unchanged(lambda: self.scoped('--uninstall'))

    def assert_guides(self, home, prompt):
        guides = [home / '.kit-resources/services' / name for name in GUIDES]
        for guide in (guides[0], guides[-1]):
            self.assertIn(str(guide), prompt)
        for guide in guides:
            self.assertTrue(guide.is_file())
            self.assertNotIn('{{', guide.read_text())
        # Every actual Markdown link in the installed index resolves there.
        for link in re.findall(r'\]\(([^)]+)\)', guides[0].read_text()):
            self.assertTrue((guides[0].parent / link).is_file())
        self.assertNotIn(str(SRC), prompt.replace(str(self.root), '<fixture>'))
        self.assertNotIn(str(self.package / 'services'), prompt)
        return guides

    def test_scoped_guides_permissions_and_catalog_boundaries(self):
        self.install_scope()
        chief = (self.domain / '.opencode/agents/example-chief.md').read_text()
        guides = self.assert_guides(self.domain, chief)
        for role in ('chief', 'lead', 'worker'):
            prompt = (self.domain / f'.opencode/agents/example-{role}.md').read_text()
            rules = json.loads(prompt.split('---')[1])['permissions']
            self.assertEqual(rules[0], dict(action='*', resource='*', effect='deny'))
            def effect(action, resource):
                return [r['effect'] for r in rules if fnmatch.fnmatchcase(action, r['action'])
                        and fnmatch.fnmatchcase(str(resource), r['resource'])][-1]
            for guide in guides:
                self.assertEqual(effect('external_directory', guide), 'allow')
                for path in (guide, guide.relative_to(self.domain)):
                    self.assertEqual(effect('read', path), 'allow')
                    self.assertEqual(effect('edit', path), 'deny')
            for sibling in (self.domain / '.kit-resources/private.md',
                            self.domain / '.kit-resources/services/private.md'):
                self.assertEqual(effect('read', sibling), 'deny')
                self.assertEqual(effect('edit', sibling), 'deny')
            for path in (self.package / 'services/README.md', self.home / 'private/secret.md',
                         self.home / '.config/chief-of-staff/goal-bindings/example/binding.json'):
                self.assertEqual(effect('external_directory', path), 'deny')
            binding = self.home / '.config/chief-of-staff/goal-bindings/example/binding.json'
            for action in ('read', 'edit', 'external_directory'):
                self.assertEqual(effect(action, binding), 'deny')
            # Existing relative *.md edit rules also match absolute names;
            # external-directory gating and canEdit enforce the outer boundary.
            # This packaging check claims neither native evaluation nor a sandbox.
            for action in ('shell', 'execute', 'a2a_send', 'session.create', 'subagent'):
                self.assertEqual(effect(action, '*'), 'deny')
        config = (self.domain / '.opencode/plugins/chief-domain/index.ts').read_text()
        for guide in guides:
            self.assertIn(str(guide), config)

    def test_legacy_scoped_absent_resources_upgrade_and_rollback(self):
        self.install_scope()
        inventory = self.domain / '.kit-install.json'
        data = json.loads(inventory.read_text())
        for p in [self.domain / '.kit-resources/services' / name for name in GUIDES]:
            data['owned'].pop(str(p.relative_to(self.home)))
            p.unlink()
        inventory.write_text(json.dumps(data))
        self.install_scope()
        self.assertEqual(self.scoped('--uninstall').returncode, 0)

    def test_default_guides_owned_update_removal_and_collisions(self):
        self.env['CHIEF_BRIEF_DIR'] = str(self.home / 'custom-memory')
        result = self.run_install('opencode')
        self.assertEqual(result.returncode, 0, result.stderr)
        memory = self.home / 'custom-memory'
        prompt = (self.home / '.config/opencode/agents/chief-of-staff.md').read_text()
        guides = self.assert_guides(memory, prompt)
        # Frozen repair roles serialize permissions inline as JSON. Parse through
        # the existing dual-format adapter; retain every original resource check.
        from access_policy import agent_parts
        rules = agent_parts(prompt)[2]
        for guide in guides:
            self.assertIn(dict(action='read', resource=str(guide), effect='allow'), rules)
        self.assertIn(dict(action='edit', resource=f'{memory}/.kit-resources/*', effect='deny'), rules)
        def effect(action, path):
            return [r['effect'] for r in rules if r['action'] == action
                    and fnmatch.fnmatchcase(str(path), r['resource'])][-1]
        for guide in guides:
            for p in (guide, guide.relative_to(memory)):
                self.assertEqual(effect('read', p), 'allow')
                self.assertEqual(effect('edit', p), 'deny')
        for p in (memory / '.kit-resources/private.md', memory / '.kit-resources/services/private.md'):
            self.assertEqual(effect('read', p), 'deny')
            self.assertEqual(effect('edit', p), 'deny')
        seed = memory / 'principal.md'
        seed.write_text('private fixture')
        self.assertEqual(self.run_install('opencode').returncode, 0)
        target = guides[-1]
        original = target.read_text()
        target.write_text(original + '\nmodified fixture')
        for args in (('opencode',), ('--uninstall', 'opencode')):
            self.assert_blocked_unchanged(lambda: self.run_install(*args))
        target.write_text(original)
        self.assertEqual(self.run_install('--uninstall', 'opencode').returncode, 0)
        self.assertTrue(all(not g.exists() for g in guides))
        self.assertEqual(seed.read_text(), 'private fixture')
        target.write_text('unowned fixture')
        self.assert_blocked_unchanged(lambda: self.run_install('opencode'))
        target.unlink()
        target.symlink_to(self.root / 'absent')
        self.assert_blocked_unchanged(lambda: self.run_install('opencode'))

    def test_legacy_scoped_new_resource_collision_refuses_all_writes(self):
        self.install_scope()
        inventory = self.domain / '.kit-install.json'
        data = json.loads(inventory.read_text())
        guides = [self.domain / '.kit-resources/services' / name for name in GUIDES]
        for p in guides:
            data['owned'].pop(str(p.relative_to(self.home)))
            p.unlink()
        inventory.write_text(json.dumps(data))
        guides[-1].write_text('unowned fixture')
        for call in (self.scoped, lambda: self.scoped('--uninstall')):
            self.assert_blocked_unchanged(call)

    def test_default_partial_host_removal_retains_shared_guides(self):
        result = self.run_install('opencode', 'claude')
        self.assertEqual(result.returncode, 0, result.stderr)
        guide = self.home / '.chief-of-staff/.kit-resources/services/directory/README.md'
        original = guide.read_bytes()
        self.assertEqual(self.run_install('--uninstall', 'opencode').returncode, 0)
        self.assertEqual(guide.read_bytes(), original)
        self.assertTrue((self.home / '.claude/agents/chief-of-staff.md').is_file())
        self.assertEqual(self.run_install('--uninstall', 'claude').returncode, 0)
        self.assertFalse(guide.exists())

    def test_rendered_inventory_is_generic_across_defaults_and_scope(self):
        for host in ('opencode', 'claude', 'codex'):
            result = self.run_install('--print', host)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('{{', result.stdout)
            self.assertNotRegex(result.stdout, r'three speech|already adopted|ALREADY been adopted')
            self.assertIn("Check the operator's existing registry", result.stdout)
        result = self.scoped('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotRegex(result.stdout, r'three speech|already adopted|ALREADY been adopted')
        self.assertFalse(self.snapshot())


if __name__ == '__main__':
    unittest.main()
