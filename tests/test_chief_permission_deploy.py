"""Permission deployment preserves installed instructions and every other role."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import agent_parts, winner
spec = importlib.util.spec_from_file_location('permission_deploy', ROOT / 'scripts/install-chief-permissions.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class ChiefPermissions(unittest.TestCase):
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
