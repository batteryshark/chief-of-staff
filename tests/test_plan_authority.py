"""Fictional rendered-text contracts, not an authority classifier or live actions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import render, lead_prompt, owner_values, pack_values
from pi_render import compose
from effective_roles import effective


class ApprovedPlanAuthority(unittest.TestCase):
    def surfaces(self):
        for host, lead, chief, shape in (
            ('opencode', 'opencode-lead.md', 'opencode.md', 'opencode-command.md'),
            ('claude', 'claude-lead-agent.md', 'claude-agent.md', 'skill.md'),
            ('codex', 'codex-lead.config.toml', 'codex.config.toml', 'skill.md'),
        ):
            yield host, effective('hosts/' + lead, '/fiction/chief', ['shape', 'worker-dispatch']), effective(
                'hosts/' + chief, '/fiction/chief', ['shape', 'worker-dispatch']), render(
                'workflows/shape/hosts/' + shape, '/fiction/chief')
        for caps in ([], ['pi-subagents', 'pi-goal-x']):
            home = Path('/fiction/home')
            outputs, _, _ = compose(home, home / 'brief', caps)
            base = home / '.pi/agent'
            yield 'pi ' + str(caps), outputs[base / 'prompts/chief-lead.md'], outputs[
                base / 'prompts/chief-of-staff.md'], outputs[base / 'skills/chief-shape/SKILL.md']

    def test_covered_install_service_push_no_repeat_approval(self):
        # Fiction: approved toy plan installs Widget, runs its preview service and
        # pushes to toy/example's preview branch. This is no live publishing authority.
        for name, lead, chief, shape in self.surfaces():
            with self.subTest(surface=name):
                for text in (lead, chief):
                    for phrase in ('authorizes everything it names or clearly implies',
                                   'installs/downloads, background services',
                                   'or push destinations', 'Do not ask again inside that authority',
                                   'Fleet on macOS in the same step',
                                   'existing project is authorization as recorded'):
                        self.assertIn(phrase, text)
                self.assertIn('initial project-plan approval, not each worker', lead)
                self.assertIn('operational or worker plan', chief)

    def test_new_money_data_hands_and_explicit_constraints_reserved(self):
        # Fiction: toy preview now wants a paid account or to erase the person's
        # photo archive; neither is explicitly approved. A covered login needs hands.
        for name, lead, chief, shape in self.surfaces():
            with self.subTest(surface=name):
                for text in (lead, chief):
                    for phrase in ('destruction of principal data require an explicit principal',
                                   'never an implication from a convenient technical dependency',
                                   "principal's hands, not another approval",
                                   'never borrow credentials or bypass authentication',
                                   'Tool-level permissions and safety constraints still stand',
                                   'fetch-only/no-push', 'not silently erase an old ban'):
                        self.assertIn(phrase, text)
                if name.startswith('pi'):
                    self.assertIn('outward actions not', lead)
                    self.assertIn('not already explicitly approved', lead)
                else:
                    self.assertIn('outward actions/destinations must be named', lead)
                    self.assertIn('unplanned outward effects', lead)

    def test_uncertain_coverage_chief_answers_without_principal_fyi(self):
        # Fiction: worker asks whether the preview dependency is covered. Lead
        # asks chief, not the person; chief reads the record and resolves coverage.
        for name, lead, chief, shape in self.surfaces():
            with self.subTest(surface=name):
                if name.startswith('pi'):
                    self.assertIn('ask the chief first with the approved plan and principal', lead)
                    self.assertIn('direct-principal standalone lead has no chief', lead)
                    self.assertIn('invent no chief channel', lead)
                    self.assertIn('read the approved plan and principal record and ANSWER it yourself', chief)
                    self.assertIn('Do not forward a technical coverage answer or send a principal FYI', chief)
                else:
                    for text in (lead, chief):
                        self.assertIn('For uncertain coverage, leads ask the chief', text)
                        self.assertIn('answers without forwarding or a principal FYI', text)
                        self.assertIn('with no invented\nchief channel', text)
                self.assertNotIn('say one sentence\n  for the principal', chief)
                self.assertNotIn('Get an explicit yes first for anything destructive', chief)

    def test_shape_upfront_fields_and_pi_seams(self):
        for name, lead, chief, shape in self.surfaces():
            with self.subTest(surface=name):
                for phrase in ('Setup: <foreseeable installs/downloads',
                               'Hands: <account sign-ins', 'Publication: <publishing/push destinations',
                               'explicit principal decisions for any non-model spending',
                               'not a dependency inventory or new approval form',
                               'without forwarding or a principal FYI', 'ONE deliverable'):
                    self.assertIn(phrase, shape)
                self.assertIn('If the principal rejects the same thing twice', lead)
                if name.startswith('pi'):
                    self.assertIn('initial plan in PROJECT.md', lead)
                    self.assertIn('file fallback', chief)
                    self.assertIn('no native Knowledge adapter', chief)
                    for text in (lead, chief, shape):
                        self.assertNotIn('native OpenChamber Knowledge Plans', text)
                        self.assertNotIn('{{', text)
                    for forbidden in ('session.send', 'a2a_create', 'returnResult:'):
                        self.assertNotIn(forbidden, lead + chief)
                else:
                    self.assertIn('INITIAL PROJECT PLAN in native OpenChamber Knowledge Plans', lead)
        standalone = lead_prompt({**pack_values(['engineering']),
            **owner_values({'mode': 'principal', 'style': 'Short.'}),
            'INTRO': 'Lead', 'MODEL_POLICY': '', 'WORKER_ROUTING': '',
            'CHECKPOINT_NAME': 'checkpoint'})
        self.assertIn('No chief is required', standalone)
        self.assertIn('invent no chief channel', standalone)


if __name__ == '__main__':
    unittest.main()
