"""Permission deployment preserves installed instructions and every other role."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import agent_parts, winner
spec = importlib.util.spec_from_file_location('permission_deploy', ROOT / 'scripts/install-chief-permissions.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class ChiefPermissions(unittest.TestCase):
    def test_explicit_revision_preserves_old_archive_and_fixed_local_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve();brief=home/'brief';brief.mkdir()
            target=brief/'.opencode/agents/chief-of-staff.md';target.parent.mkdir(parents=True)
            rules=[dict(action='edit',resource='*',effect='deny'),dict(action='edit',resource=str(brief/'research/private.md'),effect='deny')]
            before='---\n'+json.dumps({'mode':'primary','model':'keep','permissions':rules})+'\n---\n<!-- managed by chief-of-staff/install.sh; lean role -->\nExact body.\n'
            target.write_text(before);other=target.with_name('lead.md');other.write_text('foreign role')
            old=brief/'archive/reset-20261022-permission/chief-of-staff.md';old.parent.mkdir(parents=True);old.write_text('preserve original archive')
            deploy.deploy(brief,home,revision='final-1',local=True,dry=True)
            self.assertEqual(target.read_text(),before)
            deploy.deploy(brief,home,revision='final-1',local=True)
            after=target.read_text();self.assertEqual(agent_parts(after)[1],agent_parts(before)[1])
            self.assertEqual(agent_parts(after)[3]['model'],'keep')
            self.assertEqual(winner('edit',str(brief/'research/private.md'),agent_parts(after)[2])['effect'],'deny')
            self.assertEqual(winner('edit',str(brief/'research/private.key'),agent_parts(after)[2])['effect'],'deny')
            backup=brief/'archive/reset-final-1-permission/chief-of-staff.local.md'
            self.assertEqual(backup.read_text(),before);self.assertEqual(old.read_text(),'preserve original archive')
            self.assertEqual(other.read_text(),'foreign role')
            self.assertTrue(deploy.deploy(brief,home,revision='final-1',local=True).startswith('same'))
            target.write_text(before)
            with self.assertRaisesRegex(ValueError,'archive collision'):deploy.deploy(brief,home,revision='final-1',local=True)
            self.assertEqual(target.read_text(),before)
            for revision in ('','..','../escape','/absolute','a/b','a\\b','a\nnext'):
                with self.assertRaisesRegex(ValueError,'safe nonempty basename'):deploy.deploy(brief,home,revision=revision,local=True)
                self.assertEqual(target.read_text(),before)
            # The default archive collision is still a refusal, not an auto-renamed backup.
            global_role=home/'.config/opencode/agents/chief-of-staff.md';global_role.parent.mkdir(parents=True);global_role.write_text(before)
            with self.assertRaisesRegex(ValueError,'archive collision'):deploy.deploy(brief,home)

    def test_installer_flag_order_and_other_modes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            target = home / '.config/opencode/agents/chief-of-staff.md'
            target.parent.mkdir(parents=True)
            before = ('---\npermissions:\n  - action: edit\n    resource: "*"\n'
                      '    effect: deny\n---\n<!-- managed by chief-of-staff/install.sh -->\n')
            target.write_text(before)
            env = {**os.environ, 'HOME': str(home), 'CHIEF_BRIEF_DIR': str(home / 'brief')}
            for args, ok in [(['--dry-run', '--chief-permissions-only'], True),
                             (['--chief-permissions-only', '--dry-run'], True),
                             (['--chief-permissions-only', 'opencode'], False),
                             (['--chief-permissions-only', '--uninstall'], False)]:
                result = subprocess.run(['bash', str(ROOT / 'install.sh'), *args],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, ok, result.stderr)
                self.assertEqual(target.read_text(), before)
            self.assertFalse((home / 'brief').exists())

    def test_permission_only_archive_dry_run_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            brief = home / 'brief'
            brief.mkdir()
            target = home / '.config/opencode/agents/chief-of-staff.md'
            target.parent.mkdir(parents=True)
            before = ('---\npermissions:\n  - action: edit\n    resource: "*"\n'
                      '    effect: deny\nmode: primary\n---\n'
                      '<!-- managed by chief-of-staff/install.sh -->\nUntouched live instructions\n')
            target.write_text(before)
            lead = target.with_name('lead.md')
            lead.write_text('protected lead')
            deploy.deploy(brief, home, dry=True)
            self.assertEqual(target.read_text(), before)
            self.assertFalse((brief / 'archive').exists())
            deploy.deploy(brief, home)
            after = target.read_text()
            self.assertEqual(before.split('\n---\n')[1], after.split('\n---\n')[1])
            self.assertEqual((brief / 'archive/reset-20261022-permission/chief-of-staff.md').read_text(), before)
            rules = agent_parts(after)[2]
            self.assertEqual(winner('edit', 'research/result.md', rules)['effect'], 'allow')
            self.assertEqual(winner('edit', 'heartbeat/status.json', rules)['effect'], 'allow')
            self.assertEqual(winner('edit', '/foreign/project/code.py', rules)['effect'], 'deny')
            for secret in ('research/server.env', 'heartbeat/private.key', str(brief / 'research/server.pem')):
                self.assertEqual(winner('edit', secret, rules)['effect'], 'deny')
            self.assertIn('mode: primary\n---', after)
            self.assertEqual(deploy.repaired(after, str(brief)), after)
            self.assertEqual(lead.read_text(), 'protected lead')
            self.assertFalse((brief / 'chief.json').exists())
            self.assertNotIn('opencode/plan', after)

    def test_json_and_inline_metadata_preserve_body_fields_and_custom_denials(self):
        rules = [dict(action='edit', resource='*', effect='deny'),
                 dict(action='edit', resource='/fixture/brief/research/private.md', effect='deny')]
        headers = [json.dumps(dict(mode='primary', model='keep', permissions=rules)),
                   'mode: primary\nmodel: keep\npermissions: ' + json.dumps(rules)]
        for header in headers:
            before = '---\n' + header + '\n---\n<!-- managed by chief-of-staff/install.sh -->\nProtected instructions\n'
            after = deploy.repaired(before, '/fixture/brief')
            self.assertEqual(agent_parts(before)[1], agent_parts(after)[1])
            if agent_parts(before)[3] is not None:
                self.assertEqual({k:v for k,v in agent_parts(before)[3].items() if k != 'permissions'},
                                 {k:v for k,v in agent_parts(after)[3].items() if k != 'permissions'})
            else:
                self.assertIn('model: keep', agent_parts(after)[0])
            self.assertEqual(deploy.repaired(after, '/fixture/brief'), after)
            self.assertEqual(winner('edit', '/fixture/brief/research/result.md', agent_parts(after)[2])['effect'], 'allow')
            self.assertEqual(winner('edit', '/fixture/brief/research/private.md', agent_parts(after)[2])['effect'], 'deny')

    def test_unmanaged_and_symlink_target_refused(self):
        with self.assertRaises(ValueError):
            deploy.repaired('unmanaged', '/brief')
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            target = home / '.config/opencode/agents/chief-of-staff.md'
            target.parent.mkdir(parents=True)
            other = home / 'protected'
            other.write_text('original')
            target.symlink_to(other)
            with self.assertRaises(ValueError):
                deploy.deploy(home, home)
            self.assertEqual(other.read_text(), 'original')


class ChiefBodyOnly(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve(); self.brief = self.home / '.chief-of-staff'
        self.brief.mkdir()
        self.global_target = self.home / '.config/opencode/agents/chief-of-staff.md'
        self.local_target = self.brief / '.opencode/agents/chief-of-staff.md'
        for target in (self.global_target, self.local_target):
            target.parent.mkdir(parents=True)
        self.header = (b'---\n# exact custom metadata, spacing and order\nmode: primary\nmodel: keep/provider\n'
                       b'color: "#abc123"\ncustom: {nested: [one, two]}\npermissions: '
                       b'[{"action":"edit","resource":"*","effect":"deny"},'
                       b'{"action":"edit","resource":"/private/*","effect":"deny"}]\n\n---\n')
        self.global_target.write_bytes(self.header + b'<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->\nOld global.\n')
        self.local_target.write_bytes(self.header + b'<!-- managed by chief-of-staff/install.sh; lean role -->\nOld local.\n')
        self.home_patch = patch.object(Path, 'home', return_value=self.home)
        self.home_patch.start(); self.addCleanup(self.home_patch.stop)

    def call(self, local=False, **overrides):
        target = self.local_target if local else self.global_target
        args = dict(revision='lean-final', local=local, body_only=True,
                    expected_sha256=overrides['expected_sha256'] if 'expected_sha256' in overrides else deploy.sha(target.read_bytes()))
        args.update(overrides)
        return deploy.deploy(self.brief, self.home, **args)

    def test_both_targets_share_normal_generated_body_preserve_exact_independent_headers(self):
        # JSON frontmatter is retained byte-for-byte too, never parsed/reserialized.
        local_header = b'---\n{ "model": "other/model", "mode": "primary", "custom": {"taste":"caf\xc3\xa9"}, "permissions": [] }\n---\n'
        self.local_target.write_bytes(local_header + deploy.split_bytes(self.local_target.read_bytes())[1])
        other = self.global_target.with_name('lead.md'); other.write_bytes(b'foreign role')
        pointer = self.brief / 'chief.json'; pointer.write_bytes(b'{"identity":"unchanged"}')
        expected_body = deploy.split_bytes(deploy.render('hosts/opencode.md', str(self.brief)).encode())[1]
        for local, target, header in ((False, self.global_target, self.header), (True, self.local_target, local_header)):
            before = target.read_bytes(); target.chmod(0o640)
            preview = self.call(local=local, dry=True)
            self.assertEqual(preview['status'], 'would-update'); self.assertEqual(target.read_bytes(), before)
            self.assertFalse(Path(preview['backup']).exists())
            result = self.call(local=local)
            self.assertEqual(result['status'], 'updated')
            self.assertEqual(deploy.split_bytes(target.read_bytes()), (header, expected_body))
            self.assertEqual(result['beforeHeaderSha256'], result['afterHeaderSha256'])
            self.assertEqual(Path(result['backup']).read_bytes(), before)
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            self.assertEqual(self.call(local=local)['status'], 'same')
            self.assertEqual(self.call(local=local, revision='no-op')['status'], 'same')
            self.assertFalse((self.brief / 'archive/reset-no-op-body').exists())
            with self.assertRaisesRegex(ValueError, 'expected current bytes'):
                self.call(local=local, expected_sha256=deploy.sha(before))
        self.assertEqual(other.read_bytes(), b'foreign role'); self.assertEqual(pointer.read_bytes(), b'{"identity":"unchanged"}')
        self.assertEqual(deploy.split_bytes(self.global_target.read_bytes())[1], deploy.split_bytes(self.local_target.read_bytes())[1])

    def test_required_safe_revision_expected_bytes_and_immutable_archive(self):
        before = self.global_target.read_bytes()
        for revision in (None, '', '..', '../escape', '/absolute', 'a/b', 'a\\b', 'a\nnext'):
            with self.assertRaisesRegex(ValueError, 'revision|basename'):
                self.call(revision=revision)
        for expected in (None, '', 'xyz', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'SHA256|expected current bytes'):
                self.call(expected_sha256=expected)
        self.assertFalse((self.brief / 'archive').exists())
        result = self.call(); backup = Path(result['backup'])
        self.global_target.write_bytes(before)
        with self.assertRaisesRegex(ValueError, 'archive collision'): self.call()
        self.assertEqual(self.global_target.read_bytes(), before); self.assertEqual(backup.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'only in body-only'):
            deploy.deploy(self.brief, self.home, expected_sha256=deploy.sha(before))

    def test_missing_unmanaged_and_ambiguous_marker_refuse_without_adoption(self):
        for content in (b'unmanaged', self.header + b'foreign\n<!-- managed by chief-of-staff/install.sh; lean role -->\n',
                        self.header + b'<!-- managed by chief-of-staff/install.sh -->\n'):
            self.global_target.write_bytes(content)
            with self.assertRaisesRegex(ValueError, 'frontmatter|exact managed'): self.call()
            self.assertEqual(self.global_target.read_bytes(), content)
        self.local_target.write_bytes(self.header + b'<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->\n')
        with self.assertRaisesRegex(ValueError, 'canonical lean chief'): self.call(local=True)
        self.global_target.unlink()
        with self.assertRaises(FileNotFoundError): self.call(expected_sha256='0' * 64)
        self.assertFalse((self.brief / 'archive').exists())

    def test_fixed_roots_and_symlinks_refuse(self):
        for brief, home in ((self.home / 'other', self.home), (self.brief, self.home / 'other')):
            with self.assertRaisesRegex(ValueError, 'fixed home'):
                deploy.deploy(brief, home, revision='lean-final', body_only=True, expected_sha256='0' * 64)
        original = self.global_target.read_bytes(); self.global_target.unlink(); self.global_target.symlink_to(self.local_target)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.call()
        self.global_target.unlink(); self.global_target.write_bytes(original)
        (self.brief / 'archive').symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.call()
        self.assertEqual(self.global_target.read_bytes(), original)

    def test_concurrent_expected_byte_change_refuses_before_backup(self):
        render = deploy.render
        def changed(*args):
            self.global_target.write_bytes(b'independent concurrent edit')
            return render(*args)
        with patch.object(deploy, 'render', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'concurrent target changed'): self.call()
        self.assertEqual(self.global_target.read_bytes(), b'independent concurrent edit')
        self.assertFalse((self.brief / 'archive').exists())

    def test_concurrent_change_before_replace_preserves_new_owner_bytes_and_backup(self):
        before = self.global_target.read_bytes(); validate = deploy.DestinationRoot.validate_all
        checks = 0
        def changed(root, targets):
            nonlocal checks
            validate(root, targets)
            if targets == [self.global_target]:
                checks += 1
                if checks == 2: self.global_target.write_bytes(b'new owner bytes')
        with patch.object(deploy.DestinationRoot, 'validate_all', new=changed):
            with self.assertRaisesRegex(ValueError, 'before replacement'): self.call()
        self.assertEqual(self.global_target.read_bytes(), b'new owner bytes')
        self.assertEqual((self.brief / 'archive/reset-lean-final-body/chief-of-staff.md').read_bytes(), before)
        self.assertEqual(list(self.global_target.parent.iterdir()), [self.global_target])

    def test_normal_shell_entry_dry_run_both_selectors_and_unknown_target_refusal(self):
        env = {**os.environ, 'HOME': str(self.home), 'CHIEF_BRIEF_DIR': str(self.brief)}
        for local, target in ((False, self.global_target), (True, self.local_target)):
            before = target.read_bytes()
            command = ['bash', str(ROOT / 'install.sh'), '--chief-body-only', '--revision', 'lean-final',
                       '--expected-sha256', deploy.sha(before), '--dry-run'] + (['--local'] if local else [])
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['target'], str(target))
            self.assertEqual(target.read_bytes(), before)
            for extra in (['--target', '/foreign'], ['opencode'], ['--uninstall'], ['--chief-permissions-only']):
                refused = subprocess.run(command + extra, env=env, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(refused.returncode, 0)
                self.assertEqual(target.read_bytes(), before)
        self.assertFalse((self.brief / 'archive').exists())
