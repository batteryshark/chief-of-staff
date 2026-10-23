import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from role_context import exposure_policy
from role_contract import permissions
from render import render


class EffectiveContext(unittest.TestCase):
    def test_preassembly_gate_preserves_access(self):
        for role in ('chief', 'lead'):
            home = str(Path('/home/test').resolve())
            rules = permissions(role, home, home + '/brief')
            self.assertIn(dict(action='execute', resource='*', effect='deny'), rules)
            self.assertEqual([r for r in rules if r['action'] == 'edit' and r['resource'] == '*'],
                             [dict(action='edit', resource='*', effect='deny')])
        self.assertIn(dict(action='edit', resource='LEAD.md', effect='allow'), rules)
        self.assertIn(dict(action='edit', resource='lead/*', effect='allow'), rules)

    def test_one_policy_self_contained_install(self):
        output = render('services/role-context.mjs', '/home/test/brief')
        self.assertNotIn('readFileSync', output)
        self.assertNotIn('./role-policy.json', output)
        self.assertIn('const policy = ' + json.dumps(exposure_policy()) + ';', output)
        for role, policy in exposure_policy().items():
            self.assertFalse(any('*' in tool for tool in policy['tools']))
            if role != 'dispatcher':
                self.assertIn('patch', policy['tools'])
                self.assertNotIn('execute', policy['tools'])
        self.assertNotIn('writer', exposure_policy())
        self.assertNotIn('build', exposure_policy())


if __name__ == '__main__':
    unittest.main()
