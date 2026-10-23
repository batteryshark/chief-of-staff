"""Focused prompt composition checks; no live dispatch or chief state writes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render, owner_values, lead_prompt, pack_values
from pi_render import compose
from effective_roles import effective, rules, effect


class QuietInbox(unittest.TestCase):
    def test_three_hosts_quiet_lead_and_conditional_chief(self):
        for host in ('opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml'):
            text = effective('hosts/' + host, '/fixture/chief', ['reporting'])
            for token in ('No routine FYIs', 'Set returnResult:false normally in both directions',
                          'original session, absolute directory, stable private reference',
                          'never duplicate effects on both transports', 'configured pointer',
                          'workers report and ask questions only to you'):
                self.assertIn(token, text)
            self.assertNotIn('send the chief one short message saying', text)
            self.assertNotIn('Milestones and serious trouble', text)
        for host in ('opencode.md', 'claude-agent.md', 'claude-output-style.md', 'codex.config.toml'):
            text = effective('hosts/' + host, '/fixture/chief', ['checkpoint', 'dispatch-events', 'reporting'])
            for token in ('returnResult:false normally', 'needed answers', 'plain chief inbox',
                          'unread or uncertain entries', 'Close asks after answer delivery',
                          'idle is not proof of completion', 'original session'):
                self.assertIn(token.lower(), text.lower())
        permissions = render('hosts/opencode-lead.md', '/fixture/chief')
        self.assertEqual(effect(permissions, 'edit', '/fixture/chief/inbox/result.md'), 'allow')
        self.assertEqual(effect(permissions, 'external_directory', '/fixture/chief/models.md'), 'allow')
        self.assertEqual(effect(permissions, 'edit', '/fixture/chief/principal.md'), 'deny')
        self.assertFalse(any(r['resource'] == '/fixture/chief/*' for r in rules(permissions)))

    def test_owner_compatibility_and_checkpoint(self):
        for owner in ({'mode': 'principal', 'style': 'Short.'},
                      {'mode': 'agent', 'label': 'Reviewer', 'pointer': '/fixture/owner.json'}):
            text = lead_prompt({**pack_values(['engineering']), **owner_values(owner),
                'INTRO': 'Lead', 'MODEL_POLICY': '', 'WORKER_ROUTING': '',
                'CHECKPOINT_NAME': 'fixture-checkpoint'})
            self.assertNotIn('{{', text)
            self.assertNotIn('notify the reporting agent briefly of', text)
            self.assertIn('Unknown chief brief path', text)
        checkpoint = render('workflows/checkpoint/hosts/skill.md', '/fixture/chief')
        self.assertIn('Read relevant inbox entries fully before processing', checkpoint)
        self.assertIn('retain unread or uncertain entries', checkpoint)
        self.assertNotIn('Tell the chief the new id', checkpoint)

    def test_pi_shared_seams_and_plain_file_inbox(self):
        for caps in ([], ['pi-subagents', 'pi-goal-x']):
            outputs, _, _ = compose(Path('/fixture/home'), Path('/fixture/home/brief'), caps)
            self.assertTrue(all('{{' not in value for value in outputs.values()))
            text = '\n'.join(value for path, value in outputs.items()
                             if path.parent.name == 'prompts' or path.parent.name == 'chief-checkpoint')
            self.assertIn('archive/inbox/', text)
            self.assertIn('Implementation writes stay within the approved project scope.', text)
            for forbidden in ('a2a_create', 'session.send', 'returnResult:', '$OPENCODE_SESSION_ID',
                              'native OpenChamber Knowledge Plans'):
                self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
