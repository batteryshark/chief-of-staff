"""Small rendered-text boundary checks, not legal advice or model-behavior evals."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from courtesy import body, skill, DESCRIPTION
from render import render
from pi_render import compose
from effective_roles import effective

SRC = Path(__file__).resolve().parents[1]


class LicensingGuidance(unittest.TestCase):
    def surfaces(self):
        yield 'courtesy', body()
        for host in ('opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml'):
            yield host, effective('hosts/' + host, '/fiction/chief', ['upstream-courtesy'])
        home = Path('/fiction/home')
        outputs, _, _ = compose(home, home / 'brief', [])
        yield 'pi inherited lead', outputs[home / '.pi/agent/prompts/chief-lead.md']

    def test_missing_file_not_a_gate_and_fork_not_outreach(self):
        for name, text in self.surfaces():
            with self.subTest(surface=name):
                flat = ' '.join(text.split())
                for phrase in ('Fork only if we modify', 'over maintainer outreach',
                               'attribution', 'the fork',
                               'Unmodified upstream code is referenced or included/vendored with its notices',
                               'whichever fits the project',
                               'missing upstream LICENSE alone is no reason to block, ask, file an issue or escalate',
                               'handle an objection if raised',
                               'operating policy does not assert a permission grant'):
                    self.assertIn(phrase, flat)

    def test_own_work_not_dependency_relicensing_and_real_risk_exception(self):
        for name, text in self.surfaces():
            with self.subTest(surface=name):
                flat = ' '.join(text.split())
                for phrase in ('our own licence for our own work', 'not to relicense copied third-party code',
                               "bundled dependencies' shipped notices", 'explicit existing terms',
                               'never strip or invent licence text', 'Skip exhaustive licence chaining or provenance audits',
                               'unless an obvious real legal risk needs attention',
                               'a missing file alone is not that exception',
                               'Actual forks, pushes and other outward steps still follow the approved plan and reserved approvals',
                               'Real bug reports', 'principal approval', 'no automatic contact or floods'):
                    # Skill uses the equivalent hyphenated adjective for its approval rule.
                    self.assertIn(phrase, flat.replace('principal-approval', 'principal approval'))

    def test_skill_parity_on_demand_and_submission_rules_unchanged(self):
        self.assertEqual((SRC / 'skills/upstream-courtesy/SKILL.md').read_text(), skill())
        self.assertTrue(skill().startswith('---\nname: upstream-courtesy\ndescription: ' + DESCRIPTION))
        self.assertLess(len(skill().splitlines()), 160)
        for phrase in ('CONTRIBUTING', 'AI-use policy', 'If AI assistance is refused, STOP',
                       "principal/user's explicit yes BEFORE ANY outward submission",
                       'Do not schedule automatic outreach.'):
            self.assertIn(phrase, body())
        for name, text in self.surfaces():
            if name not in ('courtesy', 'pi inherited lead'):
                text = render('hosts/' + name, '/fiction/chief')
                self.assertNotIn('## 1. Triage before drafting', text)
                self.assertIn('reset-upstream-courtesy', text)
            elif name == 'pi inherited lead':
                self.assertNotIn('## 1. Triage before drafting', text)
                self.assertNotIn('upstream-courtesy', text)


if __name__ == '__main__':
    unittest.main()
