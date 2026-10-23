"""Offline prompt contracts only; no live Knowledge or chief state access."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render
from lean_roles import procedures
from pi_render import compose


class ChiefDashboard(unittest.TestCase):
    def assert_policy(self, text):
        text = ' '.join(text.split())
        for token in ('/fixture/chief', 'Knowledge is a derived status view, never a ledger',
                      'Landed / Next / Your part / Updated', 'expected-old-body', 'unrelated',
                      'files are the sole portfolio ledger'):
            self.assertIn(token, text)

    def test_three_chief_hosts_and_claude_style(self):
        for host in ('opencode.md', 'claude-agent.md', 'claude-output-style.md', 'codex.config.toml'):
            with self.subTest(host=host):
                text = ' '.join(render('hosts/' + host, '/fixture/chief').split())
                self.assertIn('reset-checkpoint', text)
                text += ' ' + ' '.join(procedures('/fixture/chief')['reset-checkpoint'].split())
                self.assert_policy(text)
                for token in ('List first', 'reuse its ID', 'Todo history',
                              'never seed or auto-resync', 'pick another ledger',
                              'existing plain chief inbox'):
                    self.assertIn(token.lower(), text.lower())
                self.assertNotIn('{{', text)

    def test_checkpoint_reconciliation_is_chief_only(self):
        for host in ('opencode-command.md', 'skill.md'):
            with self.subTest(host=host):
                text = render('workflows/checkpoint/hosts/' + host, '/fixture/chief')
                for token in ('Files hold continuity; Knowledge is derived status',
                              'expected-old-body', 'Preserve unresolved asks',
                              'old-owner safe', 'successor acceptance'):
                    self.assertIn(token, text)
                self.assertNotIn('INTERNAL OPERATIONS', text)

    def test_startup_and_claude_import(self):
        text = render('kits/chief/memory/AGENTS.md', '/fixture/chief')
        self.assertIn('Files here are the portfolio record', text)
        self.assertIn('Knowledge is a derived glanceable view', text)
        self.assertNotIn('Ops alone', text)
        self.assertLessEqual(len(text.splitlines()), 12)
        self.assertIn('@AGENTS.md', render('kits/chief/memory/CLAUDE.md', '/fixture/chief'))

    def test_plain_actions_autonomy_and_stopping_across_hosts(self):
        lean_texts = [render('hosts/' + host, '/fixture/chief') for host in (
            'opencode.md', 'claude-agent.md', 'claude-output-style.md', 'codex.config.toml',
            'opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml')]
        outputs, _, _ = compose(Path('/fixture/home'), Path('/fixture/chief'), [])
        texts = [text for path, text in outputs.items() if path.parent.name == 'prompts']
        # Lean roles preserve outcomes and guardrails, not legacy spelling/host boilerplate.
        for index, text in enumerate(lean_texts):
            normalized = ' '.join(text.split()).lower()
            for token in ('simplest', 'scope', 'explicit', 'twice', '30–45', 'principal',
                          'accepted', 'safe', 'reset-worker-dispatch', 'reset-checkpoint'):
                self.assertIn(token.lower(), normalized)
            if index < 4:
                for token in ('Restart an unjustifiably stopped lead', 'parent outcomes moving',
                              'no restart until their decision', 'extra review needs a concrete risk',
                              'new priorities or scope changes go to the principal'):
                    self.assertIn(token.lower(), normalized)
            else:
                for token in ('Resume the parent outcome automatically', 'STOP project work',
                              'overrides independent work and automatic goal continuation',
                              'not a blanket project deadline', 'not a worker\'s finished slice'):
                    self.assertIn(token.lower(), normalized)
        for text in texts:
            normalized = ' '.join(text.split())
            for token in ('EXACT', 'recommendation/default', 'Nothing needed from you',
                          'NAMED CONCRETE REMAINING RISK', 'Accepted work stays accepted',
                          'critical-path access', 'covered operational choices',
                          'MATERIAL TRADEOFF', 'MAJOR DETOUR', 'disproportionate',
                          'parent outcome ownership', 'dependencies and detours',
                          'without a principal nudge', 'THAT SIDE EFFECT',
                          'independent authorized implementation or preparation',
                          'ready-to-use or ready for the EXACT hands step',
                          'remaining gated effect', 'WHO and WHAT is needed',
                          'Keep the parent goal active until accepted complete, parked by the principal, or all useful safe paths require unavailable external input',
                          'same-thing-rejected-twice STOP rule', 'overrides continuing work',
                          'WHAT CONTINUES', 'ownership restart', 'a completed slice is not goal completion',
                          'principal is not the release manager' if '\n# Lead\n' in text else 'not as release manager'):
                self.assertIn(token.lower(), normalized.lower())
            self.assertNotIn('{{', text)
    def test_pi_fallback_and_composition_seams(self):
        for caps in ([], ['pi-subagents'], ['pi-goal-x'], ['pi-subagents', 'pi-goal-x']):
            with self.subTest(caps=caps):
                outputs, _, _ = compose(Path('/fixture/home'), Path('/fixture/chief'), caps)
                chief = outputs[Path('/fixture/home/.pi/agent/prompts/chief-of-staff.md')]
                checkpoint = outputs[Path('/fixture/home/.pi/agent/skills/chief-checkpoint/SKILL.md')]
                for text in (chief, checkpoint):
                    for token in ('SAME TURN', 'final reply', 'ideas.md',
                                  'sync unavailable/out of sync', 'no native Knowledge adapter'):
                        self.assertIn(token, text)
                    for forbidden in ('openchamber_knowledge', 'knowledge.save', 'expected-old-body',
                                      'maintain your own OpenChamber Project Knowledge', '{{'):
                        self.assertNotIn(forbidden, text)
                for path, text in outputs.items():
                    self.assertNotIn('{{', text)
                    if path.parent.name == 'prompts':
                        self.assertEqual(text.count('$ARGUMENTS'), 1)
                        self.assertTrue(text.rstrip().endswith('$ARGUMENTS'))


if __name__ == '__main__':
    unittest.main()
