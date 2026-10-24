"""Root shaping exception against rendered V2 ordered path rules; no live edits."""
from pathlib import Path
import posixpath
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render
from role_contract import project_config
from access_policy import agent_parts, winner


class LeadProjectPermission(unittest.TestCase):
    def test_brand_new_unenrolled_project_matrix(self):
        # Documented V2 internal resources are Location-relative normalized paths.
        # No project config, native session, roster or filesystem setup is involved.
        rules = agent_parts(render('hosts/opencode-lead.md', '/fixture/brief'))[2]
        for directory in ('/fixture/brand-new-project', '/another/new/location'):
            for resource in ('LEAD.md', 'PROJECT.md', 'lead/log.md', 'lead/deep/result.md'):
                with self.subTest(directory=directory, resource=resource):
                    self.assertEqual(winner('edit', resource, rules)['effect'], 'allow')
            for resource in ('src/main.py', 'README.md', 'nested/PROJECT.md',
                             '../foreign/LEAD.md', '/foreign/PROJECT.md',
                             '/foreign/lead/log.md', 'lead/../../foreign/LEAD.md',
                             'lead/../src/main.py', 'lead/.env', 'lead/private.key',
                             'lead/private.pem', '/fixture/brief/secrets/token'):
                with self.subTest(directory=directory, resource=resource):
                    self.assertEqual(winner('edit', posixpath.normpath(resource), rules)['effect'], 'deny')
        self.assertFalse(any(r['effect'] == 'allow' and r['resource'] in
                             ('*', '*/LEAD.md', '*/lead/*', '*/PROJECT.md')
                             and r['action'] == 'edit' for r in rules))

    def test_root_only_exception_and_existing_boundaries(self):
        # Fresh directories need no per-project installation for internal files.
        home, brief, project = '/fixture/home', '/fixture/brief', '/fixture/project'
        global_rules = agent_parts(render('hosts/opencode-lead.md', brief))[2]
        self.assertEqual(winner('edit', 'PROJECT.md', global_rules)['effect'], 'allow')
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
        self.assertEqual([r['resource'] for r in rules if 'PROJECT.md' in r['resource']], ['PROJECT.md', project + '/PROJECT.md'])


if __name__ == '__main__':
    unittest.main()
