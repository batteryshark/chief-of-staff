"""Root shaping exception against rendered V2 ordered path rules; no live edits."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render
from role_contract import project_config
from access_policy import agent_parts, winner


class LeadProjectPermission(unittest.TestCase):
    def test_root_only_exception_and_existing_boundaries(self):
        # Global role deliberately has no own-project grants. The installer binds
        # one exact project; do not interpret metadata layout as permission effect.
        home, brief, project = '/fixture/home', '/fixture/brief', '/fixture/project'
        global_rules = agent_parts(render('hosts/opencode-lead.md', brief))[2]
        self.assertNotEqual(winner('edit', 'PROJECT.md', global_rules)['effect'], 'allow')
        rules = project_config({}, 'lead', home, brief, project, [])['agents']['lead']['permissions']

        def effect(resource):
            return winner('edit', resource, rules)['effect']

        for path in ('PROJECT.md', 'LEAD.md', 'lead/result.md', brief + '/inbox/result.md', project + '/PROJECT.md', project + '/lead/deep/result.md'):
            with self.subTest(path=path):
                self.assertEqual(effect(path), 'allow')
        for path in ('main.ts', 'src/main.ts', 'README.md', 'nested/PROJECT.md',
                     '../other/PROJECT.md', '/other/project/PROJECT.md',
                      brief + '/principal.md', '/fixture/foreign/LEAD.md', '/fixture/foreign/lead/result.md', '.env', 'lead/server.key'):
            with self.subTest(path=path):
                self.assertEqual(effect(path), 'deny')
        self.assertEqual([r['resource'] for r in rules if 'PROJECT.md' in r['resource']], [project + '/PROJECT.md', 'PROJECT.md'])


if __name__ == '__main__':
    unittest.main()
