"""Isolated candidate seam; no live installation in these tests."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import agent_parts, winner


class CandidateInstall(unittest.TestCase):
    def test_scoped_clones_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            brief, project = home / 'brief', home / 'project'
            brief.mkdir(); project.mkdir()
            for role, location in [('chief', brief), ('lead', project)]:
                name = role + '-edit-proof-test'
                config = home / (role + '.json')
                config.write_text(json.dumps(dict(role=role, name=name, location=str(location), brief=str(brief))))
                def run(*args):
                    return subprocess.run(['bash', str(ROOT / 'install.sh'), '--candidate-config', str(config), *args], capture_output=True, text=True)
                target = location / '.opencode/agents' / (name + '.md')
                self.assertEqual(run('--dry-run').returncode, 0)
                self.assertFalse(target.exists())
                rendered = run('--print')
                self.assertEqual(rendered.returncode, 0, rendered.stderr)
                self.assertEqual(run().returncode, 0)
                text = target.read_text()
                self.assertEqual(text, rendered.stdout)
                self.assertIn('isolated candidate ' + name, text)
                rules = agent_parts(text)[2]
                if role == 'chief':
                    self.assertEqual(winner('edit', '_permission-proof-chief.md', rules)['effect'], 'allow')
                else:
                    for own in ('PROJECT.md', 'LEAD.md', 'lead/result.md', str(project / 'PROJECT.md'), str(brief / 'inbox/result.md')):
                        self.assertEqual(winner('edit', own, rules)['effect'], 'allow')
                    for foreign in ('../other/PROJECT.md', str(home / 'other/LEAD.md'), str(brief / 'principal.md'), 'src/code.py'):
                        self.assertEqual(winner('edit', foreign, rules)['effect'], 'deny')
                for action in ('shell', 'subagent', 'execute', 'openchamber', 'a2a_send', 'runway'):
                    self.assertEqual(winner(action, '*', rules)['effect'], 'deny')
                self.assertNotEqual(run().returncode, 0)
                self.assertNotEqual(run('--uninstall').returncode, 0)
                self.assertEqual(target.read_text(), text)
                self.assertFalse((location / 'chief.json').exists())
            self.assertFalse((home / '.config').exists())

    def test_wrong_chief_location_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            brief, project = root / 'brief', root / 'project'
            brief.mkdir(); project.mkdir()
            config = root / 'candidate.json'
            data = dict(role='chief', name='chief-edit-proof-test', location=str(project), brief=str(brief))
            config.write_text(json.dumps(data))
            args = ['bash', str(ROOT / 'install.sh'), '--candidate-config', str(config)]
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            data['location'] = str(brief)
            config.write_text(json.dumps(data))
            (brief / '.opencode').symlink_to(project, target_is_directory=True)
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertEqual(list(project.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
