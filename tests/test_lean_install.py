"""Final lean composition and scoped pilot roundtrip; no live role/session changes."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lean_roles as lean
from render import render
spec = importlib.util.spec_from_file_location('pilot', ROOT / 'scripts/install-reset-pilot.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class LeanInstall(unittest.TestCase):
    def test_reporting_milestone_guidance_is_explicit_load_only_and_permission_safe(self):
        procedure = lean.procedures('/brief')['reset-reporting']
        for text in ('milestone_at', 'milestone_ref', 'LEAD_CHECKINS.md', 'do not retest',
                     'For your OWN genuine accepted visible milestone, use installed `docket_milestone`',
                     'Native caller identity must match your existing enrolled row; no owner/path/env selectors.',
                     'No direct roster read/edit grant, enrollment, state change or other-row access is supplied.',
                     'Unknown outcomes need owner inspection, no retry.',
                     'Unavailable/denied tool: report the exact gap; never use shell or broader file writes.',
                     'The helper preserves0700/0600/state/other rows and checks expected bytes under flock;',
                     'that is NOT CAS against arbitrary writers or an atomic fence against session moves.'):
            self.assertIn(text, procedure)
        self.assertIn('opencode/autoinvoke: false', procedure)
        for role in ('chief', 'lead'):
            self.assertNotIn('milestone_at', lean.body(role, '/brief'))
            self.assertNotIn('lead-checkins.jsonl', lean.body(role, '/brief'))

    def test_final_role_prose_includes_catalog_tools_and_startup(self):
        for role, template in [('chief', 'opencode.md'), ('lead', 'opencode-lead.md'),
                               ('chief', 'claude-agent.md'), ('lead', 'claude-lead-agent.md')]:
            text = render('hosts/' + template, '/brief')
            body = text.split('\n---\n', 1)[1]
            header = text[4:].split('\n---\n', 1)[0]
            prose = '\n'.join(l for l in header.splitlines() if l.startswith(('name:', 'description:')))
            startup = None
            if template.startswith('claude') and role == 'chief':
                startup = ('<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->\n'
                           + (ROOT / 'kits/reset/AGENTS.md').read_text()
                           + '<!-- managed by chief-of-staff/install.sh -->\n@AGENTS.md\n')
            result = lean.budget(role, body, '/brief', header_prose=prose, startup=startup)
            self.assertLessEqual(result['lines'], lean.LIMITS[role][0])
            self.assertGreater(result['catalog_lines'], 20)  # existing skills AND Runway schema prose
            self.assertNotIn('## Host:', body)
            self.assertNotIn('skills/', body)
            with self.assertRaises(ValueError):
                lean.budget(role, body, '/brief', header_prose=prose, startup='extra rule\n' * 151)
        chief = render('hosts/opencode.md', '/brief')
        self.assertIn('Messages and notifications to the principal use Nod; calls use Voicestack', chief)
        self.assertIn('Do not switch recipients to an unproved bus', chief)

    def test_native_permissions_preserved_and_all_ids_resolve(self):
        for role, template in [('chief', 'opencode.md'), ('lead', 'opencode-lead.md')]:
            before = (ROOT / 'hosts' / template).read_text()[4:].split('\n---\n', 1)[0]
            after = render('hosts/' + template, '/brief')[4:].split('\n---\n', 1)[0]
            before = before[before.index('permissions:'):].replace('{{BRIEF_DIR}}', '/brief')
            before = before.replace('{{RUNWAY_WORKFLOW}}', str(ROOT / 'routing/WORKFLOW.md'))
            before = before.replace('{{HOME_INFRA}}', str(Path.home() / '.local/share/chief-of-staff/home-infra.md'))
            from role_contract import agent
            expected = agent(role, str(Path.home()), '/brief')[4:].split('\n---\n', 1)[0]
            self.assertEqual(after, expected)
            for ident in re.findall(r'`(reset-[a-z-]+)`', lean.body(role, '/brief')):
                self.assertIn(ident, lean.procedures('/brief'))

    def test_pilot_roundtrip_preserves_unrelated_config_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); location = root / 'chief'; location.mkdir()
            config = {'role': 'chief', 'name': 'chief-reset-staged-test',
                      'location': str(location), 'brief': str(location)}
            unrelated = location / '.opencode/opencode.json'; unrelated.parent.mkdir()
            unrelated.write_text('{"plugins":["owned-by-heartbeat"]}\n')
            pilot.run(config, 'dry')
            self.assertFalse((location / '.opencode/agents').exists())
            pilot.run(config, 'install'); pilot.run(config, 'install')
            role = location / '.opencode/agents/chief-reset-staged-test.md'
            self.assertTrue(role.is_file())
            self.assertIn('opencode/autoinvoke: false',
                          (location / '.opencode/skills/reset-reporting/SKILL.md').read_text())
            pilot.run(config, 'uninstall')
            self.assertFalse(role.exists())
            self.assertTrue((location / '.opencode/reset-install/chief-reset-staged-test-archived/.opencode/agents/chief-reset-staged-test.md').exists())
            self.assertEqual(unrelated.read_text(), '{"plugins":["owned-by-heartbeat"]}\n')

    def test_changed_pilot_and_symlinks_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config = {'role': 'lead', 'name': 'lead-reset-staged-test', 'location': str(root), 'brief': str(root)}
            pilot.run(config, 'install')
            role = root / '.opencode/agents/lead-reset-staged-test.md'; role.write_text('new owner edit')
            with self.assertRaises(ValueError): pilot.run(config, 'uninstall')
            self.assertEqual(role.read_text(), 'new owner edit')

    def test_disabled_watched_plugin_never_imports_changing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config = {'role': 'chief', 'name': 'chief-reset-staged-plugin', 'location': str(root), 'brief': str(root),
                      'heartbeat': {'enabled': False, 'pilotSessionID': 'ses_fixture', 'source': str(root / 'not-copied/plugin.mjs')}}
            pilot.run(config, 'install')
            wrapper = root / '.opencode/plugins/chief-reset-staged-plugin-heartbeat.js'
            script = 'const m=await import(' + json.dumps(wrapper.as_uri()) + '); await m.default.setup();'
            subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True)
            self.assertFalse((root / 'not-copied').exists())
            self.assertIn('chiefPointer', wrapper.read_text())
            config['heartbeat']['enabled'] = True
            with self.assertRaises(ValueError): pilot.plan(config)
