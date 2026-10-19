"""N1 full-host composition regressions; no native delivery or installation."""
import unittest

from hygiene_fixtures import outputs, pinned_print
import test_modular as modular

render, SRC = modular.render, modular.SRC


class DeskHostRoutingTests(unittest.TestCase):
    setUp = modular.ModularTests.setUp
    run_install = modular.ModularTests.run_install

    def test_complete_claude_and_codex_optin_delivery(self):
        for template, host_marker in (
                ('hosts/claude-lead-agent.md', '## Host: Claude Code'),
                ('hosts/codex-lead.config.toml', '## Host: Codex')):
            with self.subTest(template=template):
                text = render.render(template, str(self.home), desk_project='fixture')
                # Inspect the ENTIRE generated output, not just the core prompt.
                for forbidden in ('--session <chief id>', "If the chief's session id in `LEAD.md`",
                                  'the chief reads it from there', 'Otherwise record the escalation'):
                    self.assertNotIn(forbidden, text)
                notes = text.split(host_marker, 1)[1]
                for phrase in ('chief-openchamber session send',
                               '--session <freshly resolved recipient session>',
                               '--dir <freshly resolved recipient directory>',
                               'resolve', '"project":"fixture"', '"lead":"<actual lead session id>"',
                               'invalid', 'block delivery', 'no direct-chief fallback',
                               'Uncertain delivery', 'true chief', 'not authority'):
                    self.assertIn(phrase, notes)
                self.assertIn('No desk-originated Goal:', text)
                self.assertIn('A message from the chief that starts with "Goal:"', text)

    def test_nonoptin_all_19_bytes_unchanged_since_hygiene_checkpoint(self):
        baseline = self.root / 'hygiene-checkpoint'
        before = outputs(pinned_print('00c205e', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        from courtesy_fixtures import existing_outputs
        after = existing_outputs(outputs(result.stdout, SRC, self.home))
        self.assertEqual(len(after), 19)
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
