"""Offline exact installed-config amendment fixtures; no host/native access."""
import json
import copy
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runway import promo_install as pi

SOURCE = Path(__file__).resolve().parents[1]


class AmendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'opencode.jsonc'
        self.before = '{\n// unrelated fixture\n"providers":{"existing":{"opaque":"fixture-only"}},\n"unknown":true,\n}\n'
        snippet = json.loads((SOURCE / 'routing/api-promo.opencode.json').read_text())
        self.additions = {k: snippet[k] for k in ('providers', 'agents')}
        agent = self.additions['agents']['api-promo-review']
        legacy_agent = {**agent, 'steps': 1}
        legacy_agent = {k: legacy_agent[k] for k in ('description', 'mode', 'steps', 'system', 'permissions')}
        legacy = copy.deepcopy({**self.additions, 'agents': {'api-promo-review': legacy_agent}})
        legacy['providers']['anthropic-promo']['body']['max_tokens'] = 2048
        self.legacy = legacy
        after, edits = pi.splice(self.before, legacy, True)
        routes_before = '{"existing":true}\n'
        routes_after, route_edits = pi.splice(routes_before, {'promo': {'fixture': True}})
        self.config.write_text(after)
        self.routes = self.root / 'routes.json'
        self.routes.write_text(routes_after)
        self.receipt = {'files': [
            {'path': str(self.config), 'existed': True, 'before': pi.sha(self.before),
             'after': pi.sha(after), 'edits': edits, 'mode': 0o640},
            {'path': str(self.routes), 'existed': True, 'before': pi.sha(routes_before),
             'after': pi.sha(routes_after), 'edits': route_edits, 'mode': 0o600}]}
        self.journal = self.root / 'promo-install.json'
        pi.atomic(self.journal, json.dumps(self.receipt), 0o600)
        self.config.chmod(0o640)
        self.routes.chmod(0o600)
        self.money = self.root / 'promo.sqlite3'
        self.money.write_bytes(b'opaque-money-fixture-do-not-open')

    def amend(self, apply=False):
        return pi.amend(SOURCE, self.config, self.root, apply)

    def test_dry_run_then_exact_apply_preserves_original_and_money(self):
        snapshot = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertTrue(self.amend()['dry_run'])
        self.assertEqual(snapshot, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertTrue(self.amend(True)['amended'])
        new = json.loads(self.journal.read_text())
        self.assertEqual(pi.unsplice(self.config.read_text(), new['files'][0]), self.before)
        self.assertEqual(new['files'][0]['before'], self.receipt['files'][0]['before'])
        self.assertEqual(new['files'][1], json.loads(json.dumps(self.receipt['files'][1])))
        self.assertEqual(self.routes.read_bytes(), snapshot['routes.json'])
        self.assertEqual(self.money.read_bytes(), snapshot['promo.sqlite3'])
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o640)
        self.assertNotIn('fixture-only', self.journal.read_text())
        with self.assertRaises(ValueError):
            self.amend(True)  # deliberately not a general updater

    def test_current_no_steps_2048_transition_and_recovery(self):
        legacy = copy.deepcopy(self.legacy)
        del legacy['agents']['api-promo-review']['steps']
        old, edits = pi.splice(self.before, legacy, True)
        self.config.write_text(old)
        self.receipt['files'][0].update(after=pi.sha(old), edits=edits)
        pi.atomic(self.journal, json.dumps(self.receipt), 0o600)
        real = pi.atomic
        def stop(path, text, mode):
            if path == self.journal:
                raise OSError('fixture receipt interruption')
            real(path, text, mode)
        with patch.object(pi, 'atomic', stop), self.assertRaises(OSError):
            self.amend(True)
        self.assertTrue(self.amend()['resume'])
        self.amend(True)
        current = json.loads(self.journal.read_text())
        self.assertEqual(pi.unsplice(self.config.read_text(), current['files'][0]), self.before)
        self.assertEqual(current['files'][1], json.loads(json.dumps(self.receipt['files'][1])))

    def test_no_steps_prefill_and_retained_controls(self):
        agent = self.additions['agents']['api-promo-review']
        self.assertNotIn('steps', agent)
        self.assertEqual(agent['permissions'], [{'action': '*', 'resource': '*', 'effect': 'deny'}])
        self.assertIn('Do not request tools or continuation', agent['system'])
        provider = self.additions['providers']['anthropic-promo']
        self.assertEqual(provider['body']['max_tokens'], 8192)
        self.assertEqual(provider['models']['claude-haiku-5-5']['body']['max_tokens'], 32)

    def test_refuse_changed_postimage_mode_or_route_without_writes(self):
        for path, change in ((self.config, 'text'), (self.config, 'mode'),
                             (self.routes, 'text'), (self.routes, 'mode'), (self.journal, 'mode')):
            with self.subTest(path=path.name, change=change):
                before, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
                if change == 'text':
                    path.write_bytes(before + b' ')
                else:
                    path.chmod(0o644)
                snapshot = {p.name: p.read_bytes() for p in self.root.iterdir()
                            if p.name != '.promo-install.lock'}
                with self.assertRaises(ValueError):
                    self.amend(True)
                self.assertEqual(snapshot, {p.name: p.read_bytes() for p in self.root.iterdir()
                                           if p.name != '.promo-install.lock'})
                path.write_bytes(before)
                path.chmod(mode)

    def test_interruption_at_each_replace_resumes_forward(self):
        real_atomic = pi.atomic
        # Before config, before receipt, or after receipt but before journal deletion.
        for fail_at in (2, 3, 4):
            with self.subTest(fail_at=fail_at):
                old_config = pi.splice(self.before, self.legacy, True)[0]
                real_atomic(self.config, old_config, 0o640)
                real_atomic(self.journal, json.dumps(self.receipt), 0o600)
                count = 0

                def interrupted(path, text, mode):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError('fixture interruption')
                    real_atomic(path, text, mode)
                    if fail_at == 4 and count == 3:
                        raise OSError('fixture after receipt')

                with patch.object(pi, 'atomic', interrupted), self.assertRaises(OSError):
                    self.amend(True)
                pending = self.root / 'promo-amend.json'
                self.assertEqual(stat.S_IMODE(pending.stat().st_mode), 0o600)
                self.assertNotIn('fixture-only', pending.read_text())
                with self.assertRaises(ValueError):
                    pi.rollback(self.root)
                self.assertTrue(self.amend()['resume'])
                self.assertTrue(self.amend(True)['amended'])
                self.assertFalse(pending.exists())

    def test_interrupted_amendment_refuses_foreign_edit(self):
        real = pi.atomic

        def stop(path, text, mode):
            if path == self.config:
                raise OSError('fixture interruption')
            real(path, text, mode)

        with patch.object(pi, 'atomic', stop), self.assertRaises(OSError):
            self.amend(True)
        self.config.write_text(self.config.read_text() + ' ')
        snapshot = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaises(ValueError):
            self.amend(True)
        self.assertEqual(snapshot, {p.name: p.read_bytes() for p in self.root.iterdir()})


if __name__ == '__main__':
    unittest.main()
