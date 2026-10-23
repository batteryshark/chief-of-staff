"""Ordinary offline render/install contracts; no agent dispatch or live records."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC / 'scripts'))
from render import render, read, STRATEGIC_SKILLS, strategic_skill
from pi_render import compose
from effective_roles import effective


class IntegratedUplift(unittest.TestCase):
    def test_current_startup_uses_declared_memory_not_retired_private_history(self):
        for brief in ('/fixture/chief', '/fixture/other'):
            startup = render('kits/chief/memory/AGENTS.md', brief)
            self.assertIn('Chief memory bootstrap', startup)
            self.assertIn('brief.md', startup)
            self.assertLessEqual(len(startup.splitlines()), 12)
            checkpoint = render('workflows/checkpoint/hosts/skill.md', brief)
            self.assertIn('existing record', checkpoint)
            self.assertIn('unread or uncertain', checkpoint)
            self.assertNotIn('INTERNAL OPERATIONS', startup + checkpoint)

    def test_authority_once_in_explicit_shape_scenario_and_retired_front_refuses(self):
        authority = read('kits/shared/approved-plan-authority.md')
        for host, lead, chief, suffix in (
                ('opencode', 'opencode-lead.md', 'opencode.md', '.md'),
                ('claude', 'claude-lead-agent.md', 'claude-agent.md', '.md'),
                ('codex', 'codex-lead.config.toml', 'codex.config.toml', '.config.toml')):
            for template in (lead, chief):
                text = effective('hosts/' + template, '/fiction/brief', ['shape'])
                self.assertEqual(text.count(authority), 1)
                self.assertNotIn('{{', text)
                self.assertNotIn('## Build the outlook', text)
                self.assertNotIn('Obtain independent initial views', text)
            for retired in (host + '-ops' + suffix, host + '-front-door' + suffix):
                with self.assertRaises(KeyError):
                    render('hosts/' + retired, '/fiction/brief')

    def test_truth_retention_and_transport(self):
        chief = effective('hosts/opencode.md', '/fiction/brief', ['checkpoint', 'dispatch-events', 'reporting'])
        for phrase in ('sole portfolio ledger', 'Knowledge is a derived status view, never a ledger',
                       'Preserve unresolved items, holds, results', 'denied access is a reported limitation',
                       'original session, absolute directory, private', 'targeted delivery', 'not a private answer'):
            if phrase == 'not a private answer':
                self.assertIn('never a private answer', chief)
            else:
                self.assertIn(phrase, chief)
        lead = effective('hosts/opencode-lead.md', '/fiction/brief', ['reporting'])
        self.assertIn('Set returnResult:false normally in both directions', lead)
        self.assertIn('No routine FYIs', lead)
        self.assertIn('late receipts/PENDING cannot', lead)
        self.assertIn('never duplicate effects on both transports', lead)
        for name in STRATEGIC_SKILLS:
            self.assertIn(name, lead)

    def test_on_demand_procedures_and_no_frozen_forecast(self):
        outlook = strategic_skill('delivery-outlook')
        for phrase in ('OWNER', 'UNKNOWN', 'was', 'DIAGNOSTIC CUE', 'uncertainty reduction',
                       'percentage is optional', 'next demonstrable milestone', 'required tests'):
            self.assertIn(phrase, outlook)
        self.assertNotIn('27 November', outlook)
        comparative = strategic_skill('comparative-review')
        for phrase in ('independent initial views before cross-pollination', 'ORIGINAL model',
                       'named accountable synthesizer', 'dissent', 'decision owner',
                       'decision-ready', 'No binding vote'):
            self.assertIn(phrase, comparative)
        for name in ('Astra', 'Fable'):
            self.assertNotIn(name, comparative)

    def test_pi_exports_discovery_without_transport_or_default_procedures(self):
        home = Path('/fiction/home')
        outputs, _, _ = compose(home, home / 'brief', [])
        for role in ('chief-of-staff', 'chief-lead'):
            prompt = outputs[home / f'.pi/agent/prompts/{role}.md']
            for name in STRATEGIC_SKILLS:
                self.assertIn(name, prompt)
            for phrase in ('session.send', 'returnResult:', '{{', '## Build the outlook'):
                self.assertNotIn(phrase, prompt)
            self.assertEqual(prompt.count(read('kits/shared/approved-plan-authority.md')), 1)
        for name in STRATEGIC_SKILLS:
            self.assertEqual(outputs[home / f'.pi/agent/skills/{name}/SKILL.md'], strategic_skill(name))

    def test_host_install_readback_idempotency_and_unowned_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            env = {**os.environ, 'HOME': str(home), 'CHIEF_BRIEF_DIR': str(home / 'brief')}
            def install(*args):
                return subprocess.run(['bash', str(SRC / 'install.sh'), *args],
                                      env=env, capture_output=True, text=True, timeout=30)
            for _ in range(2):
                result = install('opencode', 'claude', 'codex')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for base in ('.config/opencode', '.claude', '.codex'):
                for name in STRATEGIC_SKILLS:
                    text = (home / base / 'skills' / name / 'SKILL.md').read_text()
                    self.assertEqual(text, strategic_skill(name).rstrip() + '\n')
            target = home / '.config/opencode/skills/delivery-outlook/SKILL.md'
            target.write_text('User owned\n')
            self.assertNotEqual(install('opencode').returncode, 0)
            self.assertEqual(target.read_text(), 'User owned\n')
            target.unlink()
            elsewhere = home / 'user-skill.md'
            elsewhere.write_text('User owned\n')
            target.symlink_to(elsewhere)
            self.assertNotEqual(install('opencode').returncode, 0)
            self.assertEqual(elsewhere.read_text(), 'User owned\n')

    def test_pi_previous_inventory_can_add_only_named_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            env = {**os.environ, 'HOME': str(home), 'CHIEF_BRIEF_DIR': str(home / 'brief')}
            def install():
                return subprocess.run(['bash', str(SRC / 'install.sh'), '--profile', 'pi'],
                                      env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(install().returncode, 0)
            inventory = home / '.config/chief-of-staff/pi-install.json'
            data = json.loads(inventory.read_text())
            for name in STRATEGIC_SKILLS:
                key = f'.pi/agent/skills/{name}/SKILL.md'
                del data['owned'][key]
                (home / key).unlink()
            inventory.write_text(json.dumps(data))
            result = install()
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in STRATEGIC_SKILLS:
                self.assertEqual((home / f'.pi/agent/skills/{name}/SKILL.md').read_text(), strategic_skill(name))
            # Removing an old owned resource is not an authorized inventory migration.
            data = json.loads(inventory.read_text())
            del data['owned']['.pi/agent/prompts/chief-lead.md']
            inventory.write_text(json.dumps(data))
            self.assertNotEqual(install().returncode, 0)
