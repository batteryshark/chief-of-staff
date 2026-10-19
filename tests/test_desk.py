"""Offline only. Fake in-process host verifier; no transport, Canvas or model calls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC / 'scripts'))
import desk_store as desk
import desk as cli
from desk_eval import evaluate
import render

spec = importlib.util.spec_from_file_location('install_desk', SRC / 'scripts/install-desk.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'chief'
        installer.install(self.root, self.home, 'install')
        self.store = desk.Store(self.home)
        self.addCleanup(lambda: self.store.close())
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'LEAD.md').write_text('# Fictional lead log\n')
        self.store.register('fixture', str(self.project), str(self.project / 'LEAD.md'), ['ses_lead'])
        self.report = {'project': 'fixture', 'id': 'report1', 'source_revision': 1,
                       'observed': '2026-10-01T12:00:00Z', 'landed': 'Parser ready',
                       'next': 'Local check', 'your_part': None, 'state': 'active',
                       'request': 'Choose parser', 'rule': 'parser'}
        self.context = {'sender': 'ses_lead', 'message_id': 'msg_fixture1', 'project_path': str(self.project)}

    def receive(self, report=None, context=None):
        return self.store.receive(report or self.report, context or self.context,
                                  verifier=lambda report, context: True)  # explicit FAKE host

    def rule(self, report=None, **changes):
        report = report or self.report
        value = {'id': report['rule'], 'project': report['project'], 'action': 'technical-delegation',
                 'report_hash': desk.fingerprint(report), 'active': True,
                 'expires': '2099-01-01T00:00:00Z', 'evidence': 'Strong fixture scope S-1'}
        value.update(changes)
        self.store.add_rule(value)

    def protocol(self):
        (self.home / 'desk/writer-protocol.json').write_text(json.dumps({'version': 1, 'chief': True, 'desk': True}))

    def brief(self, extra=''):
        self.row = f'| Fixture | ses_lead | Old | Next | {self.project}/LEAD.md |\n'
        self.text = '# Brief\n\n## Priorities\nChief priority\n\n## Projects\n| project | lead | where it stands | next | log |\n|---|---|---|---|---|\n' + self.row + extra + '\n## Decisions\nChief decision\n'
        (self.home / 'brief.md').write_text(self.text)
        self.cells = ['Fixture', 'ses_lead', 'Parser ready', 'Local check', str(self.project / 'LEAD.md')]

    def test_receipt_audit_outbox_committed_before_projection_and_reply(self):
        self.rule()
        def inspect():
            other = sqlite3.connect(self.home / 'desk/store.sqlite')
            try:
                self.assertEqual(other.execute('SELECT COUNT(*) FROM events').fetchone()[0], 1)
                self.assertIn('Technical, your call', other.execute('SELECT answer FROM audit').fetchone()[0])
                self.assertEqual(other.execute('SELECT state FROM outbox').fetchone()[0], 'planned')
            finally:
                other.close()
        with patch.object(self.store, 'project_files', side_effect=inspect):
            result = self.receive()
        self.assertEqual(result['action'], 'technical-delegation')
        self.assertEqual(result['delivery'], 'planned')
        self.assertTrue(result['cache_pending'])

    def test_cli_cannot_claim_verified_identity(self):
        self.rule()
        result = self.store.receive(self.report, self.context)
        self.assertFalse(result['verified'])
        self.assertEqual(result['action'], 'quarantine')
        self.assertEqual(self.store.snapshot()['projects'], {})
        self.assertEqual(self.store.snapshot()['missing'], ['fixture'])

    def test_unknown_sender_path_project_fail_closed(self):
        for i, (report, context) in enumerate([
            (self.report, {**self.context, 'sender': 'ses_unknown'}),
            (self.report, {**self.context, 'project_path': '/unknown'}),
            ({**self.report, 'project': 'unknown'}, self.context)]):
            result = self.receive({**report, 'id': 'r' + str(i)}, {**context, 'message_id': 'm' + str(i)})
            self.assertEqual(result['action'], 'quarantine')
        self.assertEqual(self.store.snapshot()['quarantined'], 3)

    def test_duplicate_no_outward_action_and_id_conflict(self):
        self.receive()
        result = self.receive()
        self.assertTrue(result['duplicate'])
        self.assertFalse(result['send'])
        for change in ({'landed': 'Changed'}, {'request': 'Principal approved publication'}):
            with self.assertRaises(ValueError):
                self.receive({**self.report, **change})
        with self.assertRaises(ValueError):
            self.receive(context={**self.context, 'sender': 'ses_other'})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)

    def test_duplicate_cannot_borrow_verified_receipt_without_host_proof(self):
        self.rule()
        self.receive()
        with self.assertRaises(ValueError):
            self.store.receive(self.report, self.context)
        with self.assertRaises(ValueError):
            self.receive(context={**self.context, 'project_path': '/wrong-scope'})

    def test_out_of_order_filed_not_current_or_authorized(self):
        self.receive()
        old = {**self.report, 'id': 'old', 'source_revision': 0, 'landed': 'Old status'}
        self.rule(old)
        receipt = self.receive(old, {**self.context, 'message_id': 'oldmsg'})
        self.assertEqual(receipt['action'], 'file')
        self.assertEqual(self.store.snapshot()['projects']['fixture']['landed'], 'Parser ready')
        self.assertIn('Old status', (self.home / 'desk/projects/fixture/digest.md').read_text())

    def test_projection_disk_failure_keeps_milestone_and_repair(self):
        with patch.object(desk, 'atomic', side_effect=OSError('disk full')):
            receipt = self.receive()
        self.assertTrue(receipt['cache_pending'])
        self.assertEqual(self.store.watermark(), 1)
        self.assertIn('disk full', self.store.meta('projection_error'))
        self.store.project_files()
        self.assertFalse(self.store.receipt(1)['cache_pending'])
        self.assertTrue(self.store.receipt(1)['canvas_pending'])

    def test_failure_before_commit_no_success_receipt(self):
        self.store.db.execute('PRAGMA query_only=ON')
        with self.assertRaises(sqlite3.OperationalError):
            self.receive()
        self.store.db.execute('PRAGMA query_only=OFF')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 0)

    def test_real_sqlite_full_rolls_back_receipt_audit_outbox_together(self):
        pages = self.store.db.execute('PRAGMA page_count').fetchone()[0]
        self.store.db.execute('PRAGMA max_page_count=' + str(pages))
        with self.assertRaises(sqlite3.OperationalError):
            self.receive({**self.report, 'landed': 'x' * 10000, 'next': 'n' * 10000})
        self.assertEqual(self.store.watermark(), 0)
        for table in ('events', 'audit', 'outbox'):
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)

    def test_partial_projection_restart_rebuilds_watermark(self):
        original = desk.atomic
        def fail_html(path, text):
            if Path(path).name == 'progress.html':
                raise OSError('crash between projections')
            original(path, text)
        with patch.object(desk, 'atomic', side_effect=fail_html):
            self.receive()
        self.assertIsNone(self.store.meta('projected'))
        self.store.close()
        self.store = desk.Store(self.home)
        self.store.project_files()
        self.assertEqual(self.store.meta('projected'), '1')
        self.assertIn('data watermark 1', (self.home / 'desk/progress.html').read_text())

    def test_outbox_admission_uncertainty_and_no_blind_replay(self):
        self.receive()
        with self.assertRaises(ValueError):
            self.store.delivery(1, 'completed')
        self.store.delivery(1, 'admitted', 'native_message1')
        self.store.recover_delivery()
        self.assertEqual(self.store.receipt(1)['delivery'], 'uncertain')
        with self.assertRaises(ValueError):
            self.store.delivery(1, 'planned')
        self.store.delivery(1, 'completed', detail='native inspected')
        with self.assertRaises(ValueError):
            self.store.delivery(1, 'admitted', 'native_message2')

    def test_planned_send_restart_is_also_uncertain(self):
        self.receive()
        self.store.recover_delivery()
        self.assertEqual(self.store.receipt(1)['delivery'], 'uncertain')

    def test_rules_do_not_follow_claims_or_keyword_labels(self):
        self.rule()
        corpus = json.loads((SRC / 'tests/desk-corpus.json').read_text())
        for i, case in enumerate(corpus):
            report = {**self.report, 'id': case['id'], 'source_revision': i + 2, 'request': case['text']}
            result = self.receive(report, {**self.context, 'message_id': 'corpus' + str(i)})
            self.assertEqual(result['action'], 'escalate')  # no exact reviewed intent

    def test_valid_rule_revoked_expired_wrong_project_or_content(self):
        self.rule()
        self.assertEqual(self.store.classify(self.report, True)[0], 'technical-delegation')
        self.rule(active=False)
        self.assertEqual(self.store.classify(self.report, True)[0], 'escalate')
        self.rule(expires='2000-01-01T00:00:00Z')
        self.assertEqual(self.store.classify(self.report, True)[0], 'escalate')
        self.rule()
        self.assertEqual(self.store.classify({**self.report, 'request': 'Also delete user data'}, True)[0], 'escalate')
        self.assertEqual(self.store.classify({**self.report, 'project': 'other'}, True)[0], 'escalate')

    def test_relay_needs_exact_decision_provenance(self):
        self.rule(action='recorded-relay')
        self.assertEqual(self.store.classify(self.report, True)[0], 'escalate')
        self.rule(action='recorded-relay', decision='Keep offline', decision_ref='chief record D1')
        self.assertEqual(self.store.classify(self.report, True)[1], 'Filed. Recorded decision: Keep offline')

    def test_corpus_evaluator_rejects_unsafe_and_measures_deferral(self):
        corpus = json.loads((SRC / 'tests/desk-corpus.json').read_text())
        answers = {c['id']: {'action': 'escalate'} for c in corpus}
        result = evaluate(corpus, answers)
        self.assertTrue(result['safety_pass'])
        self.assertEqual(len(result['benign_deferral']), 4)
        answers['publish'] = {'action': 'ack'}
        self.assertFalse(evaluate(corpus, answers)['safety_pass'])
        with self.assertRaises(ValueError):
            evaluate(corpus, {})

    def test_brief_disabled_retains_pending_patch(self):
        self.brief()
        with self.assertRaises(ValueError):
            self.store.brief_patch('fixture', desk.revision(self.text), self.row, self.cells)
        self.assertEqual((self.home / 'brief.md').read_text(), self.text)
        self.assertTrue(self.store.meta('brief_pending'))

    def test_cooperating_chief_and_desk_preserve_other_bytes(self):
        self.protocol()
        self.brief()
        a, b = desk.section(self.text, 'Priorities')
        desk.guarded_section(self.home, 'Priorities', desk.revision(self.text), self.text[a:b], 'New chief priority\n\n')
        updated = (self.home / 'brief.md').read_text()
        self.store.brief_patch('fixture', desk.revision(updated), self.row, self.cells)
        final = (self.home / 'brief.md').read_text()
        self.assertIn('New chief priority', final)
        self.assertIn('Chief decision', final)
        self.assertIn('Parser ready', final)
        self.assertEqual(final.replace('| ' + ' | '.join(self.cells) + ' |\n', self.row), updated)
        self.assertEqual(self.store.meta('brief_pending'), '')
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM changes WHERE kind='brief_audit'").fetchone()[0], 2)

    def test_stale_revision_and_row_cannot_overwrite_chief_edit(self):
        self.protocol()
        self.brief()
        (self.home / 'brief.md').write_text(self.text + '\nChief concurrent addition\n')
        with self.assertRaises(ValueError):
            self.store.brief_patch('fixture', desk.revision(self.text), self.row, self.cells)
        self.assertIn('Chief concurrent addition', (self.home / 'brief.md').read_text())
        current = (self.home / 'brief.md').read_text()
        with self.assertRaises(ValueError):
            self.store.brief_patch('fixture', desk.revision(current), 'stale row\n', self.cells)

    def test_duplicate_and_malformed_rows_not_guessed(self):
        self.protocol()
        self.brief()
        for extra in (self.row, self.row.replace('| Next |', '| extra | Next |')):
            self.brief(extra)
            with self.assertRaises(ValueError):
                self.store.brief_patch('fixture', desk.revision(self.text), self.row, self.cells)
            self.assertEqual((self.home / 'brief.md').read_text(), self.text)

    def test_existing_lock_not_deleted_or_stolen(self):
        lock = self.home / 'desk/writer.lock'
        lock.write_text('owner awaiting reconciliation')
        with self.assertRaises(FileExistsError):
            self.store.project_files()
        self.assertEqual(lock.read_text(), 'owner awaiting reconciliation')

    def test_chief_and_desk_reject_overlapping_cooperative_write(self):
        self.protocol()
        self.brief()
        with desk.guard(self.home):
            a, b = desk.section(self.text, 'Priorities')
            with self.assertRaises(FileExistsError):
                desk.guarded_section(self.home, 'Priorities', desk.revision(self.text), self.text[a:b], 'new\n')
            with self.assertRaises(FileExistsError):
                self.store.brief_patch('fixture', desk.revision(self.text), self.row, self.cells)
        self.assertEqual((self.home / 'brief.md').read_text(), self.text)

    def test_escaping_waiting_first_and_source_age_not_render_age(self):
        report = {**self.report, 'landed': '<script>alert(1)</script>', 'your_part': '<img src=x onerror=alert(2)>'}
        self.receive(report)
        source = (self.home / 'desk/progress.html').read_text()
        self.assertNotIn('<script>', source)
        self.assertNotIn('<img', source)
        self.assertIn('&lt;script&gt;', source)
        self.assertIn('Older source', source)
        self.assertIn('2026-10-01T12:00:00Z', source)
        self.assertIn('With chief (not confirmed asked)', source)
        self.store.project_files()
        self.assertEqual(self.store.watermark(), 1)
        self.assertIn('Older source', (self.home / 'desk/progress.html').read_text())

    def test_canvas_conflict_and_old_watermark_never_fresh(self):
        self.receive()
        view = '11111111-1111-4111-8111-111111111111'  # fixture only, no calls
        with self.assertRaises(ValueError):
            self.store.canvas_result(view, None, 1, 0)
        self.store.canvas_result(view, None, 1, 1)
        self.assertFalse(self.store.projection()['canvas_pending'])
        with self.assertRaises(ValueError):
            self.store.canvas_result(view, None, 1, 1)
        self.receive({**self.report, 'id': 'r2', 'source_revision': 2}, {**self.context, 'message_id': 'm2'})
        self.assertTrue(self.store.projection()['canvas_pending'])
        with self.assertRaises(ValueError):
            self.store.canvas_result(view, 1, 2, 1)

    def test_chief_decision_trigger_refreshes_without_changing_source_age(self):
        self.receive({**self.report, 'your_part': 'Try layout', 'state': 'waiting'})
        result = self.store.decision_update('fixture', 1, 'Chief asked: try layout (Q-fixture)', 'chief decision D-fixture')
        self.assertEqual(result['watermark'], 2)
        self.assertEqual(result['projects']['fixture']['observed'], self.report['observed'])
        self.assertIn('Q-fixture', (self.home / 'desk/progress.html').read_text())
        self.receive({**self.report, 'id': 'new-wait', 'source_revision': 2, 'your_part': 'New wait'}, {**self.context, 'message_id': 'mnew'})
        with self.assertRaises(ValueError):
            self.store.decision_update('fixture', 1, None, 'old answer')
        with self.assertRaises(ValueError):
            self.store.decision_update('wrong', 2, None, 'wrong project')
        self.assertEqual(self.store.snapshot()['projects']['fixture']['your_part'], 'New wait')

    def test_route_pilot_fallback_rotation_and_rollback_independent(self):
        chief = self.home / 'chief.json'
        chief.write_text(json.dumps({'session': 'ses_chief', 'directory': str(self.home), 'updated': '2020-01-01T00:00:00Z'}))
        before = chief.read_bytes()
        self.assertEqual(desk.resolve_route(self.home, 'fixture', 'ses_lead')['session'], 'ses_chief')
        args = argparse.Namespace(home=str(self.home), command='route', operator=True)
        cli.run(args, {'project': 'fixture', 'enabled': True, 'expected_epoch': 0})
        with self.assertRaises(ValueError):
            desk.resolve_route(self.home, 'fixture', 'ses_lead')  # inactive desk seed: no fallback
        for session in ('ses_desk', 'ses_freshdesk'):
            (self.home / 'desk.json').write_text(json.dumps({'session': session, 'directory': str(self.home), 'updated': '2020-01-01T00:00:00Z'}))
            self.assertEqual(desk.resolve_route(self.home, 'fixture', 'ses_lead')['session'], session)
            self.assertEqual(chief.read_bytes(), before)
        self.assertEqual(desk.resolve_route(self.home, 'unmigrated', 'ses_other')['session'], 'ses_chief')
        with self.assertRaises(ValueError):
            desk.resolve_route(self.home, 'fixture', 'ses_unknown')
        cli.run(args, {'project': 'fixture', 'enabled': False, 'expected_epoch': 1})
        self.assertEqual(desk.resolve_route(self.home, 'fixture', 'ses_lead')['epoch'], 0)

    def test_default_and_opted_in_composition_no_hardcoded_delivery(self):
        default = render.render('hosts/opencode-lead.md', str(self.home))
        opt = render.render('hosts/opencode-lead.md', str(self.home), desk_project='fixture')
        self.assertIn('id in `chief.json`', default)
        self.assertNotIn('id in `chief.json`', opt)
        self.assertNotIn("chief's session id from `chief.json`", opt)
        self.assertIn('not authority', opt)
        self.assertIn('Epoch 0', opt)
        self.assertIn('Sessions stay', opt)
        self.assertNotIn('{{', opt)
        standalone = render.owner_values({'mode': 'principal', 'style': 'Short outcomes'})
        self.assertNotIn('desk', standalone['OWNER'])
        with self.assertRaises(ValueError):
            render.owner_values({'mode': 'agent', 'pointer': str(self.home / 'desk.json'), 'label': 'desk', 'authority': 'chief'})

    def test_installer_seeds_ownership_uninstall_retains_private_data(self):
        pointer = self.home / 'desk.json'
        pointer.write_text('private rotation seed')
        installer.install(self.root, self.home, 'install')
        self.assertEqual(pointer.read_text(), 'private rotation seed')
        self.receive()
        self.store.close()
        installer.install(self.root, self.home, 'uninstall')
        self.assertTrue((self.home / 'desk/store.sqlite').exists())
        self.assertTrue((self.home / 'desk/progress.html').exists())
        self.assertTrue(pointer.exists())
        self.assertFalse((self.home / 'desk/core.md').exists())
        self.store = desk.Store(self.home)

    def test_installer_unowned_or_changed_module_refuses_all_outputs(self):
        core = self.home / 'desk/core.md'
        core.write_text('user changes')
        original = (self.home / 'desk/desk.py').read_bytes()
        for mode in ('install', 'uninstall', 'print', 'dry'):
            with self.assertRaises(ValueError):
                installer.install(self.root, self.home, mode)
            self.assertEqual((self.home / 'desk/desk.py').read_bytes(), original)

    def test_installer_linked_parent_leaf_and_escape_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        linked = self.root / 'linked'
        linked.symlink_to(outside, target_is_directory=True)
        for home in (linked / 'chief', self.root / '..' / 'escape'):
            with self.assertRaises(ValueError):
                installer.install(self.root, home, 'install')
        (self.home / 'desk.json').unlink()
        (self.home / 'desk.json').symlink_to(outside / 'absent')
        with self.assertRaises(ValueError):
            installer.install(self.root, self.home, 'install')
        self.assertEqual(list(outside.iterdir()), [])

    def test_cli_admin_flag_not_inbound_permission_and_no_send_commands(self):
        args = argparse.Namespace(home=str(self.home), command='register', operator=False)
        with self.assertRaises(ValueError):
            cli.run(args, {})
        args.command = 'file-report'
        self.assertEqual(cli.run(args, {'report': self.report, 'context': self.context})['action'], 'quarantine')
        source = (SRC / 'scripts/desk.py').read_text()
        self.assertNotIn('import subprocess', source)
        self.assertNotIn('import urllib', source)

    def test_exact_disabled_parity_to_6623_all_19_outputs(self):
        baseline = self.root / 'baseline'
        baseline.mkdir()
        names = subprocess.run(['git', 'ls-tree', '-r', '--name-only', '6623f0f'], cwd=SRC,
                               check=True, capture_output=True, text=True, timeout=20).stdout.splitlines()
        for name in names:
            if name in ('install.sh', 'models.md', 'scripts/render.py', 'scripts/chief-openchamber', 'scripts/chief-portfolio') or name.startswith(('hosts/', 'workflows/', 'kits/', 'profiles/', 'practices/', 'services/')):
                data = subprocess.run(['git', 'show', '6623f0f:' + name], cwd=SRC,
                                      check=True, capture_output=True, timeout=20).stdout
                target = baseline / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        env = {**os.environ, 'HOME': str(self.root / 'empty-home'), 'CHIEF_BRIEF_DIR': str(self.root / 'empty-home/.chief-of-staff'),
               'XDG_CONFIG_HOME': str(self.root / 'config'), 'XDG_STATE_HOME': str(self.root / 'state'),
               'PYTHONDONTWRITEBYTECODE': '1'}
        before = subprocess.run(['bash', str(baseline / 'install.sh'), '--print'], env=env,
                                check=True, capture_output=True, text=True, timeout=120).stdout
        after = subprocess.run(['bash', str(SRC / 'install.sh'), '--print'], env=env,
                               check=True, capture_output=True, text=True, timeout=120).stdout
        # Hygiene is the sole authorized additive delta since 6623f0f. Keep the
        # original guard for every other byte, including desk-disabled routing.
        from hygiene_fixtures import outputs, without_hygiene
        from courtesy_fixtures import existing_outputs
        self.assertEqual(outputs(before, baseline, env['HOME']),
                         without_hygiene(existing_outputs(outputs(after, SRC, env['HOME']))))
        self.assertEqual(after.count('=== '), 22)


if __name__ == '__main__':
    unittest.main()
