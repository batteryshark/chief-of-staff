"""Bounded offline source/isolated install checks; static prompts are not model evals."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from courtesy_fixtures import existing_outputs
from courtesy import body, skill, target, MARKER
from hygiene_fixtures import outputs
from effective_roles import assert_current_exports

SRC = Path(__file__).resolve().parent.parent


class CourtesyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        tmp = self.root / 'tmp'
        tmp.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'TMPDIR': str(tmp),
                    'XDG_CONFIG_HOME': str(self.root / 'config'),
                    'XDG_STATE_HOME': str(self.root / 'state'),
                    'XDG_CACHE_HOME': str(self.root / 'cache'),
                    'CHIEF_BRIEF_DIR': str(self.home / '.chief-of-staff'),
                    'PYTHONDONTWRITEBYTECODE': '1'}
        transport = self.root / 'transport/src/plugin.js'
        transport.parent.mkdir(parents=True)
        transport.write_text('// Synthetic transport fixture; hashed, never loaded.\nexport default {};\n')
        self.env.update(CHIEF_A2A_MODULE=str(transport), CHIEF_A2A_ROOT=str(transport.parent.parent))

    def install(self, *args, ok=True):
        p = subprocess.run(['bash', str(SRC / 'install.sh'), *args], env=self.env,
                           capture_output=True, text=True, timeout=25)
        self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
        return p.stdout

    def snapshot(self):
        return {str(p.relative_to(self.home)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.home.rglob('*') if p.is_file() and not p.is_symlink()}

    def config(self, packs):
        p = self.root / 'lead.json'
        p.write_text(json.dumps(dict(version=1, agent='courtesy-test', packs=packs,
                                    owner=dict(mode='principal', style='Short outcomes.'))))
        return str(p)

    def test_canonical_parity_portability_and_static_cases(self):
        self.assertEqual((SRC / 'skills/upstream-courtesy/SKILL.md').read_text(), skill())
        self.assertEqual(skill().split(MARKER + '\n\n', 1)[1], body() + '\n')
        self.assertLessEqual(len(skill().splitlines()), 160)
        for forbidden in ('/Users/', 'https://', 'http://', 'ses_', 'runway', 'lead/'):
            self.assertNotIn(forbidden, skill())
        data = json.loads((SRC / 'skills/upstream-courtesy/evals/evals.json').read_text())
        self.assertEqual(len(data['evals']), 3)
        self.assertFalse(data['trigger_checks'][0]['should_trigger'])
        self.assertTrue(all(e['expected_output'] and e['files'] == [] for e in data['evals']))

    def test_approved_lean_export_delta_and_exact_courtesy_leaves(self):
        now = outputs(self.install('--print'), SRC, self.home)
        assert_current_exports(self, now, SRC, self.home, self.home / '.chief-of-staff')
        corrupted = dict(now)
        path = '<HOME>/.claude/skills/upstream-courtesy/SKILL.md'
        corrupted[path] += '!'
        with self.assertRaises(AssertionError):
            assert_current_exports(self, corrupted, SRC, self.home, self.home / '.chief-of-staff')

    def test_default_all_hosts_reinstall_and_uninstall_retain_user_data(self):
        self.install()
        for host in ('opencode', 'claude', 'codex'):
            self.assertEqual(target(self.home, host).read_text(), skill())
        before = self.snapshot()
        self.install()
        self.assertEqual(before, self.snapshot())
        user = target(self.home, 'claude').parent / 'private-notes.md'
        user.write_text('private')
        self.install('--uninstall')
        self.assertEqual(user.read_text(), 'private')
        self.assertTrue((self.home / '.chief-of-staff/principal.md').exists())
        self.assertFalse(target(self.home, 'claude').exists())

    def test_new_targets_preflight_nonoverwrite_symlink_and_parent_all_hosts(self):
        for host in ('opencode', 'claude', 'codex'):
            with self.subTest(host=host):
                p = target(self.home, host)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('user skill')
                before = self.snapshot()
                self.install(ok=False)
                self.assertEqual(before, self.snapshot())
                p.unlink()
                p.symlink_to(self.root / 'missing')
                self.install(ok=False)
                self.assertTrue(p.is_symlink())
                p.unlink()
                p.parent.rmdir()
                p.parent.symlink_to(self.root, target_is_directory=True)
                self.install(ok=False)
                p.parent.unlink()

    def test_standalone_all_domains_optin_has_no_prompt_delta(self):
        for pack in ('engineering', 'research'):
            plain = self.install('--print', '--lead-config', self.config([pack]))
            extra = self.install('--print', '--lead-config', self.config([pack, 'upstream-courtesy']))
            self.assertEqual(plain, extra)
            self.install('--lead-config', self.config([pack, 'upstream-courtesy']))
            for host in ('opencode', 'claude', 'codex'):
                text = target(self.home, host).read_text()
                self.assertEqual(text.split('\n\n', 1)[1], body() + '\n')
            self.assertFalse((self.home / '.chief-of-staff').exists())
            self.install('--uninstall', '--lead-config', self.config([pack]))
            self.assertFalse(any(p.is_file() for p in self.home.rglob('*')))

    def test_standalone_reuses_default_skill_without_claiming_or_removing(self):
        self.install()
        baseline = self.snapshot()
        args = ('--lead-config', self.config(['research']))
        self.install(*args)
        for path, digest in baseline.items():
            self.assertEqual(self.snapshot()[path], digest)
        self.install('--uninstall', *args)
        self.assertEqual(self.snapshot(), baseline)

    def test_standalone_new_skill_preflight_all_hosts(self):
        args = ('--lead-config', self.config(['research']))
        for host in ('opencode', 'claude', 'codex'):
            p = target(self.home, host)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('user skill')
            before = self.snapshot()
            self.install(*args, ok=False)
            self.assertEqual(before, self.snapshot())
            p.unlink()
            p.parent.rmdir()
            p.parent.symlink_to(self.root, target_is_directory=True)
            self.install(*args, ok=False)
            p.parent.unlink()

    def test_scoped_new_skill_parent_preflight_before_any_write(self):
        p = self.home / '.chiefs/example/.opencode/skills/upstream-courtesy'
        p.parent.mkdir(parents=True)
        p.symlink_to(self.root, target_is_directory=True)
        before = self.snapshot()
        self.install('--profile', 'example', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_scoped_skill_permissions_no_worker_prompt_and_retain_seeds(self):
        self.install('--profile', 'example')
        home = self.home / '.chiefs/example'
        p = home / '.opencode/skills/upstream-courtesy/SKILL.md'
        self.assertEqual(p.read_text().split('\n\n', 1)[1], body() + '\n')
        for role in ('chief', 'lead', 'worker'):
            text = (home / f'.opencode/agents/example-{role}.md').read_text()
            header = json.loads(text.split('---')[1])
            self.assertIn(dict(action='skill', resource='upstream-courtesy', effect='allow'), header['permissions'])
            self.assertNotIn('upstream-courtesy', text.split('---', 2)[2])
        before = self.snapshot()
        self.install('--profile', 'example')
        self.assertEqual(before, self.snapshot())
        (home / 'principal.md').write_text('private')
        self.install('--uninstall', '--profile', 'example')
        self.assertEqual((home / 'principal.md').read_text(), 'private')
        self.assertFalse(p.exists())

    def test_scoped_skill_preflight_and_prior_inventory_additive_upgrade(self):
        self.install('--profile', 'example')
        home = self.home / '.chiefs/example'
        inv = home / '.kit-install.json'
        data = json.loads(inv.read_text())
        p = home / '.opencode/skills/upstream-courtesy/SKILL.md'
        del data['owned'][str(p.relative_to(self.home))]
        # A real pre-courtesy inventory also predates the public guide-copy
        # addition. Remove only this test's seven owned synthetic guide leaves;
        # a partial modern inventory is intentionally not a supported upgrade.
        from service_resources import resource_paths
        for guide in resource_paths(home):
            del data['owned'][str(guide.relative_to(self.home))]
            guide.unlink()
        inv.write_text(json.dumps(data))
        p.write_text('user skill')
        before = self.snapshot()
        self.install('--profile', 'example', ok=False)
        self.assertEqual(before, self.snapshot())
        p.unlink()
        # Model an actual pre-courtesy nine-leaf inventory, not an externally
        # deleted new leaf with its still-valid receipt (which must refuse).
        from courtesy_owned import OwnedSkills
        OwnedSkills(self.home, {}, rollback=True).record_path(p).unlink()
        self.install('--profile', 'example')
        self.assertEqual(len(json.loads(inv.read_text())['owned']), 17)  # includes seven public guide leaves


if __name__ == '__main__':
    unittest.main()
