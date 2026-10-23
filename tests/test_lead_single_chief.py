"""Current rendered lead routing, without live sends or session changes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render
from lean_roles import procedures


class LeadSingleChief(unittest.TestCase):
    def test_current_routing_and_answer_safety(self):
        prompt = render('hosts/opencode-lead.md', '/brief')
        self.assertIn('Load `reset-reporting` before escalation or applying an answer', prompt)
        prompt += procedures('/brief')['reset-reporting']
        for text in (
            '/brief/chief.json',
            'Re-read the configured pointer before sending',
            'never\nuse cached retired addresses or title-search substitutes',
            'returnResult:false normally in both directions',
            'stable private reference, scope and limits',
            'Retain original session, absolute directory',
            'Apply only a matching answer. Ignore resolved duplicates',
            'never a private answer or approval',
            'Never guess, impersonate an owner\nor silently switch targets',
        ):
            with self.subTest(text=text):
                self.assertIn(text, prompt)
        for text in ('Ops when split roles are active', 'lead→live Ops',
                     'Ops→ORIGINAL lead', 'On OpenChamber routes to Ops',
                     'ses_examplee7ce9ac21681'):
            with self.subTest(text=text):
                self.assertNotIn(text, prompt)


if __name__ == '__main__':
    unittest.main()
