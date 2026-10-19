"""Offline Pi loading paths and lifecycle; never execute Pi or an extension."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from pi_render import compose
from render import pack_values

SRC = Path(__file__).resolve().parent.parent


class PiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='chief-pi-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir(mode=0o700)
        self.package = self.root / 'relocated'
        shutil.copytree(SRC, self.package, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.home),
                    'TMPDIR': str(self.root), 'PYTHONDONTWRITEBYTECODE': '1',
                    **{f'XDG_{k}_HOME': str(self.root / k.lower())
                       for k in ('CONFIG', 'DATA', 'STATE', 'CACHE')}}

    def run_install(self, *args, caps=(), pi=True):
        options = ['--profile', 'pi'] if pi else []
        for cap in caps:
            options.extend(['--pi-capability', cap])
        return subprocess.run(['/bin/bash', str(self.package / 'install.sh'), *options, *args],
                              cwd=self.home, env=self.env, text=True, capture_output=True, timeout=10)

    def ok(self, *args, **kwargs):
        result = self.run_install(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def snapshot(self):
        return {str(p.relative_to(self.home)): ('link', str(p.readlink())) if p.is_symlink()
                else ('dir', p.stat().st_mode) if p.is_dir()
                else ('file', p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in self.home.rglob('*')}

    def refused(self, *args, **kwargs):
        before = self.snapshot()
        result = self.run_install(*args, **kwargs)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(before, self.snapshot(), result.stderr)

    def test_loading_paths_metadata_and_independent_options(self):
        for caps in ((), ('pi-subagents',), ('pi-goal-x',), ('pi-subagents', 'pi-goal-x')):
            before = self.snapshot()
            preview = self.ok('--print', caps=caps)
            self.ok('--dry-run', caps=caps)
            self.assertEqual(before, self.snapshot())
            self.ok(caps=caps)
            base = self.home / '.pi/agent'
            for name in ('chief-of-staff', 'chief-lead'):
                p = base / f'prompts/{name}.md'
                text = p.read_text()
                self.assertIn('description:', text)
                self.assertIn('argument-hint:', text)
                self.assertIn('$ARGUMENTS', text)
                self.assertEqual(text.count('$ARGUMENTS'), 1)
                self.assertIn(text, preview)
                self.assertNotIn('{{', text)
            lead = (base / 'prompts/chief-lead.md').read_text()
            chief = (base / 'prompts/chief-of-staff.md').read_text()
            for cap, token in (('pi-subagents', 'subagents_enable'), ('pi-goal-x', 'create_goal')):
                self.assertEqual(token in lead, cap in caps)
                self.assertEqual(cap in lead + chief, cap in caps)
            self.assertNotIn('create_goal', chief)
            self.assertIn('/skill:chief-shape', chief)
            self.assertNotIn('`/chief-shape`', chief)
            self.assertNotIn('These are the only files you\nwrite yourself.', lead)
            self.assertIn('Implementation writes stay within the approved project scope.', lead)
            for forbidden in ('a2a_create', 'session.send', 'returnResult:', '$OPENCODE_SESSION_ID',
                              'native OpenChamber Knowledge Plans', 'runway`'):
                self.assertNotIn(forbidden, lead + chief, forbidden)
            for name in ('chief-shape', 'chief-checkpoint', 'chief-lead-checkpoint'):
                text = (base / f'skills/{name}/SKILL.md').read_text()
                self.assertIn(f'name: {name}\n', text)
                self.assertNotIn('{{', text)
                self.assertIn(text, preview)
            self.assertFalse((base / 'extensions').exists())
            self.assertFalse((base / 'settings.json').exists())
            self.assertFalse((base / 'agents').exists())
            self.assertFalse((self.home / '.chief-of-staff/chief.json').exists())
            self.ok('--uninstall')  # Doesn't need selected optional packages.

    def test_updates_retention_guides_and_uninstall(self):
        self.ok()
        base = self.home / '.pi/agent'
        notes = base / 'skills/chief-checkpoint/user-notes.md'
        notes.write_text('user fixture')
        seed = self.home / '.chief-of-staff/principal.md'
        seed.write_text('retained fixture')
        settings = base / 'settings.json'
        settings.write_text('{"fixture": true}')
        self.ok(caps=('pi-subagents', 'pi-goal-x'))
        lead = base / 'prompts/chief-lead.md'
        self.assertIn('create_goal', lead.read_text())
        self.ok(caps=('pi-subagents',))
        self.assertNotIn('create_goal', lead.read_text())
        index = base / 'chief-resources/services/README.md'
        self.assertIn(str(index), (base / 'prompts/chief-of-staff.md').read_text())
        for name in ('models', 'runway', 'docket', 'fleet', 'voicestack', 'directory'):
            self.assertTrue((index.parent / name / 'README.md').is_file())
        self.ok('--uninstall')
        self.assertFalse(lead.exists())
        self.assertFalse(index.exists())
        self.assertEqual(notes.read_text(), 'user fixture')
        self.assertEqual(seed.read_text(), 'retained fixture')
        self.assertEqual(settings.read_text(), '{"fixture": true}')
        self.assertFalse((base / 'skills/upstream-courtesy/SKILL.md').exists())

    def test_unowned_modified_missing_and_inventory_refuse_all_modes(self):
        p = self.home / '.pi/agent/prompts/chief-lead.md'
        p.parent.mkdir(parents=True)
        p.write_text('unowned')
        for args in ((), ('--print',), ('--dry-run',), ('--uninstall',)):
            self.refused(*args)
        p.unlink()
        self.ok()
        original = p.read_bytes()
        p.write_bytes(original + b'edited')
        for args in ((), ('--uninstall',)):
            self.refused(*args)
        p.unlink()
        self.refused('--uninstall')
        p.write_bytes(original)
        inv = self.home / '.config/chief-of-staff/pi-install.json'
        saved = inv.read_text()
        for mutate in (lambda v: v.update(version=True),
                       lambda v: v['owned'].update({'../outside': '0' * 64}),
                       lambda v: v['owned'].pop('.pi/agent/prompts/chief-lead.md')):
            value = json.loads(saved)
            mutate(value)
            inv.write_text(json.dumps(value))
            self.refused('--uninstall')
        inv.write_text(saved)
        courtesy = self.home / '.pi/agent/skills/upstream-courtesy/SKILL.md'
        courtesy.write_text(courtesy.read_text() + 'edited')
        self.refused('--uninstall')

    def test_symlink_and_brief_guards(self):
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'keep'
        sentinel.write_text('unchanged')
        for rel in ('.pi', '.pi/agent/prompts', '.pi/agent/skills/chief-shape',
                    '.config/chief-of-staff', '.chief-of-staff'):
            link = self.home / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside, target_is_directory=True)
            for args in ((), ('--print',), ('--dry-run',), ('--uninstall',)):
                self.refused(*args)
            link.unlink()
            self.assertEqual(list(outside.iterdir()), [sentinel])
        self.env['CHIEF_BRIEF_DIR'] = str(outside)
        self.refused()
        self.env.pop('CHIEF_BRIEF_DIR')
        self.env['PI_CODING_AGENT_DIR'] = str(outside)
        self.refused()

    def test_invalid_options_never_reach_other_hosts(self):
        for caps in (('unknown',), ('pi-subagents', 'pi-subagents')):
            self.refused(caps=caps)
        for args in (('opencode',), ('--routing',), ('--lead-config', 'absent')):
            self.refused(*args)
        self.refused('--print', 'opencode', caps=('pi-subagents',), pi=False)
        preview = self.ok('--print', 'opencode', pi=False)
        for token in ('pi-subagents', 'pi-goal-x', 'subagents_enable', 'create_goal', '.pi/agent'):
            self.assertNotIn(token, preview)

    def test_remaining_practices_and_removed_selection(self):
        self.assertEqual({p.name for p in (SRC / 'practices').iterdir() if p.is_dir()},
                         {'engineering', 'research', 'upstream-courtesy'})
        for packs in (['engineering'], ['research'], ['engineering', 'research'],
                      ['research', 'upstream-courtesy']):
            self.assertTrue(pack_values(packs))
        with self.assertRaisesRegex(ValueError, 'no longer shipped'):
            pack_values(['life-admin'])

    def test_original_host_render_bytes_unchanged(self):
        # Derived independently from a95f4e81 output, normalizing only fixture
        # source/HOME roots. No private historical Git object needed at test time.
        expected = {
            'opencode': '847581d5ef8251a503ecad5646972046638c99931b5af158989d04b3c00aeff4',
            'claude': '0faadc20cf25782be69e16c23f3695fa9b63ee880bdb6983e3476c637718d2ca',
            'codex': 'a0e8bb7883a9b4728e1537abdcc04af86ffc399a7667c7a3ad35595fe38b048b'}
        for host, digest in expected.items():
            after = self.ok('--print', host, pi=False)
            normalized = after.replace(str(self.package), '<source>').replace(str(self.home), '<home>')
            self.assertEqual(hashlib.sha256(normalized.encode()).hexdigest(), digest)

    def test_removed_practice_refuses_in_scoped_manifest_without_mutation(self):
        config = json.loads((self.package / 'profiles/example/profile.json').read_text())
        config['lead_packs'] = ['life-admin']
        path = self.root / 'old-scope.json'
        path.write_text(json.dumps(config))
        before = self.snapshot()
        result = self.run_install('--profile', str(path), pi=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no longer shipped', result.stderr)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
