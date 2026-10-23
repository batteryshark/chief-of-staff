"""Local Git fixtures and fake native APIs; no dispatch or model requests."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from runway.cli import LocalAPI, compact_plan, handle, status_text
from runway.ledger import Ledger
from test_routing import NOW, fixture, timestamp


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q')
        self.git(self.repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-q', '--allow-empty', '-m', 'fixture')
        self.wt = self.repo / 'wt' / 'pi-followup'
        self.git(self.repo, 'worktree', 'add', '-q', '-b', 'pi-followup', str(self.wt))
        self.ledger = Ledger(self.root / 'ledger.sqlite3')
        self.addCleanup(self.ledger.close)
        self.config, self.snapshot, self.catalog, self.task = fixture()
        self.task.update(directory=str(self.repo), scope=str(self.repo), checkout=str(self.wt))
        self.catalog['directory'] = str(self.repo)
        self.host = Mock()
        self.host.catalog.return_value = self.catalog
        self.quota = Mock()
        self.quota.get.return_value = self.snapshot

    def git(self, directory, *args):
        return subprocess.run(['git', '-C', str(directory), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def prepare(self, **changes):
        return self.ledger.plan(self.config, self.snapshot, self.catalog,
                                {**self.task, **changes}, NOW, admit=True)

    def session(self, a, directory=None):
        provider, model = a['model'].split('/', 1)
        return {'id': 'ses_fixture', 'location': {'directory': directory or str(self.repo)},
                'model': {'providerID': provider, 'id': model}}

    def evidence(self):
        return dict(session_id='ses_fixture', idle=True, inbox_empty=True, outcome='succeeded',
                    tools_reconciled=True, effects_reconciled=True, last_idle_at=timestamp(NOW + 2))

    def checkpoint(self):
        return dict(objective='fix', directory=str(self.repo), checkout=str(self.wt),
                    changes='source', tests='passed', next='review', side_effects='none')

    def test_nested_native_session_admits_binds_and_shows_both_locations(self):
        result = self.prepare()
        self.assertTrue(result['dispatch_allowed'])
        self.assertEqual(result['args']['directory'], str(self.repo))
        self.assertNotIn('checkout', result['args'])
        a = self.ledger.bind(result['attempt']['id'], self.session(result['attempt']), NOW + 1)
        self.assertEqual(a['task']['checkout'], str(self.wt))
        compact = compact_plan(result)['attempt']
        self.assertEqual(compact['directory'], str(self.repo))
        self.assertEqual(compact['checkout'], str(self.wt))
        with patch('runway.cli.time.time', return_value=NOW):
            text = status_text(self.config, self.ledger, self.snapshot, str(self.repo))
        self.assertIn('directory ' + str(self.repo), text)
        self.assertIn('checkout ' + str(self.wt), text)

    def test_real_session_directory_drift_still_refused(self):
        a = self.prepare()['attempt']
        with self.assertRaisesRegex(ValueError, 'worker directory'):
            self.ledger.bind(a['id'], self.session(a, str(self.wt)), NOW + 1)
        api = LocalAPI('http://127.0.0.1:1234')
        with patch.object(api, 'session', return_value=self.session(a, str(self.wt))):
            with self.assertRaisesRegex(ValueError, 'session moved'):
                api.idle_evidence('ses_fixture', str(self.repo))
            with patch.object(api, 'get', side_effect=[{'data': v} for v in ({}, [], [], [])]):
                e = api.idle_evidence('ses_fixture', str(self.repo), quota_only=True)
            self.assertTrue(e['idle'] and e['inbox_empty'])
            self.assertFalse(e['directory_matches'])
            self.assertEqual(e['session_directory'], str(self.wt))

    def test_foreign_unregistered_subdirectory_and_missing_checkout_refused(self):
        foreign = self.root / 'foreign'
        self.git(self.repo, 'clone', '-q', str(self.repo), str(foreign))
        plain = self.repo / 'unregistered'
        plain.mkdir()
        for location in (foreign, plain, self.wt / 'missing', self.repo / 'wt'):
            with self.subTest(location=location), self.assertRaises(ValueError):
                self.prepare(checkout=str(location))
        for invalid in (None, '', False):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.prepare(checkout=invalid)

    def test_checkout_is_canonicalized(self):
        result = self.prepare(checkout=str(self.wt / '..' / self.wt.name))
        self.assertEqual(result['attempt']['task']['checkout'], str(self.wt))

    def test_same_checkout_writers_conflict_even_with_different_session_directories(self):
        self.prepare()
        result = self.prepare(job='second', directory=str(self.wt))
        self.assertFalse(result['dispatch_allowed'])
        self.assertIn('writer', result['reason'])

    def test_separate_worktrees_with_same_native_directory_admitted(self):
        self.prepare()
        result = self.prepare(job='second', checkout=str(self.repo))
        self.assertTrue(result['dispatch_allowed'])
        self.assertEqual(result['args']['directory'], str(self.repo))

    def test_explicit_main_checkout_conflicts_with_legacy_main_writer(self):
        task = dict(self.task)
        task.pop('checkout')
        self.ledger.plan(self.config, self.snapshot, self.catalog, task, NOW, admit=True)
        self.assertFalse(self.prepare(job='second', checkout=str(self.repo))['dispatch_allowed'])

    def test_read_only_keeps_checkout_and_does_not_reserve_writer(self):
        a = self.prepare(writer=False)['attempt']
        self.assertFalse(a['task']['writer'])
        self.assertEqual(a['task']['checkout'], str(self.wt))
        self.assertTrue(self.prepare(job='writer')['dispatch_allowed'])

    def test_checkpoint_continuation_keeps_both_fields_and_identity(self):
        a = self.prepare()['attempt']
        self.ledger.bind(a['id'], self.session(a), NOW + 1)
        cp = self.checkpoint()
        missing = dict(cp)
        missing.pop('checkout')
        with self.assertRaisesRegex(ValueError, 'source checkout'):
            self.ledger.finish(a['id'], 'quiescent', missing, self.evidence(), NOW + 3)
        self.ledger.finish(a['id'], 'quiescent', cp, self.evidence(), NOW + 3)
        for changes in ({'directory': str(self.wt)}, {'checkout': str(self.repo)}):
            with self.assertRaisesRegex(ValueError, 'retain'):
                self.prepare(**changes)
        self.host.idle_evidence.return_value = self.evidence()
        with patch('runway.cli.time.time', return_value=NOW + 4):
            result = handle(dict(action='prepare', task=self.task, format='json'),
                            self.config, self.ledger, self.quota, self.host)
        self.host.idle_evidence.assert_called_once_with('ses_fixture', str(self.repo))
        self.host.catalog.assert_called_once_with(str(self.repo), ['gpt/strong', 'claude/strong'])
        self.assertEqual(result['action'], 'session.send')
        self.assertEqual(result['attempt']['checkpoint'], cp)
        self.assertEqual(result['attempt']['checkout_identity'], a['checkout_identity'])
        self.ledger.bind(result['attempt']['id'], self.session(result['attempt']), NOW + 5)

    def test_deleted_checkout_refused_at_bind_checkpoint_resume_not_terminal_cleanup(self):
        a = self.prepare()['attempt']
        self.ledger.bind(a['id'], self.session(a), NOW + 1)
        self.git(self.repo, 'worktree', 'remove', str(self.wt))
        with self.assertRaises(ValueError):
            self.ledger.bind(a['id'], self.session(a), NOW + 2)
        with self.assertRaises(ValueError):
            self.ledger.finish(a['id'], 'quiescent', self.checkpoint(), self.evidence(), NOW + 3)
        # Missing checkout cannot prevent uncertainty or verified terminal cleanup.
        self.ledger.finish(a['id'], 'uncertain', {}, {}, NOW + 3)
        self.ledger.finish(a['id'], 'completed', {}, self.evidence(), NOW + 4)

    def test_recreated_checkout_identity_refused_on_continuation(self):
        a = self.prepare()['attempt']
        self.ledger.bind(a['id'], self.session(a), NOW + 1)
        self.ledger.finish(a['id'], 'quiescent', self.checkpoint(), self.evidence(), NOW + 3)
        # Simulate replaced metadata without depending on filesystem inode reuse.
        a = self.ledger.get(a['id'])
        a['checkout_identity']['inode'] += 1
        self.ledger.save(a)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.prepare()

    def test_nonrepository_legacy_default_still_admits_binds_and_checkpoints(self):
        plain = self.root / 'plain'
        plain.mkdir()
        task = {**self.task, 'directory': str(plain)}
        task.pop('checkout')
        self.catalog['directory'] = str(plain)
        result = self.ledger.plan(self.config, self.snapshot, self.catalog, task, NOW, admit=True)
        a = result['attempt']
        self.assertNotIn('checkout_identity', a)
        self.ledger.bind(a['id'], self.session(a, str(plain)), NOW + 1)
        cp = self.checkpoint()
        cp.pop('checkout')
        cp['directory'] = str(plain)
        self.ledger.finish(a['id'], 'quiescent', cp, self.evidence(), NOW + 3)
        result = self.ledger.plan(self.config, self.snapshot, self.catalog, task, NOW + 4, admit=True)
        self.assertEqual(result['attempt']['checkpoint'], cp)
