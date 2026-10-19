"""Finite offline regressions for independently reproduced foundation defects."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_desk as fixtures
import desk_store as desk
import render


class FoundationFixTests(unittest.TestCase):
    setUp = fixtures.DeskTests.setUp
    receive = fixtures.DeskTests.receive

    def test_full_host_keeps_chief_goal_and_park_authority(self):
        for host in ('opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml'):
            text = render.render('hosts/' + host, str(self.home), desk_project='fixture')
            self.assertIn('outcome that the chief set', text)
            self.assertIn('A message from the chief that starts with "Goal:"', text)
            self.assertIn('If the chief tells you to park', text)
            self.assertNotIn('from the reporting recipient that starts', text)
            for clause in ('current chief decision', 'provenance', 'fail closed',
                           'Reports to the reporting recipient', 'No desk-originated'):
                self.assertIn(clause, text)

    def test_optin_composed_checkpoint_and_fresh_prompt(self):
        template = 'workflows/checkpoint/hosts/opencode-command.md'
        default = render.render(template, str(self.home))
        opt = render.render(template, str(self.home), desk_project='fixture')
        # Chief rotation instructions are byte-identical, not repurposed for desk.
        chief = default.split('\n**The chief of staff:**\n')[1].split('\n**A lead:**\n')[0]
        self.assertIn('Write your session id into chief.json', chief)
        self.assertIn(chief, opt)
        for clause in ('report project `fixture`', 'current epoch', 'trusted registry',
                       'explicit new-lead route acknowledgement', 'actual delivered report',
                       'file-only claims are not proof', 'chief.json', 'freshly resolved reporting recipient'):
            self.assertIn(clause, ' '.join(opt.split()))
        fresh = opt.split('Fresh-lead prompt:')[1]
        for clause in ('Goal:', 'read LEAD.md', 'fixture', 'epoch', 'fail closed'):
            self.assertIn(clause, fresh)

    def race_after_delivery_read(self, contender):
        self.receive()
        other = desk.Store(self.home)
        self.addCleanup(other.close)
        other.db.execute('PRAGMA busy_timeout=0')
        original = self.store.db
        outcomes = []

        class Cursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def fetchone(inner):
                row = inner.cursor.fetchone()
                try:
                    contender(other)
                    outcomes.append('won')
                except sqlite3.OperationalError:
                    outcomes.append('locked')
                return row

        class Connection:
            def __enter__(inner):
                original.__enter__()
                return inner

            def __exit__(inner, *args):
                return original.__exit__(*args)

            def execute(inner, sql, *args):
                cursor = original.execute(sql, *args)
                return Cursor(cursor) if sql.startswith('SELECT * FROM outbox WHERE seq=') else cursor

        with patch.object(self.store, 'db', Connection()):
            self.store.delivery(1, 'admitted', 'native_A', 'A admission')
        self.assertEqual(outcomes, ['locked'])
        return other

    def test_two_connection_delivery_cannot_overwrite_completed(self):
        def complete(other):
            other.delivery(1, 'admitted', 'native_B', 'B admission')
            other.delivery(1, 'completed', detail='B completion')
        other = self.race_after_delivery_read(complete)
        other.delivery(1, 'completed', detail='A completion')
        with self.assertRaises(ValueError):
            self.store.delivery(1, 'admitted', 'stale')
        row = other.db.execute('SELECT * FROM outbox').fetchone()
        self.assertEqual((row['state'], row['message_id'], row['detail']),
                         ('completed', 'native_A', 'no transport invoked\nA admission\nA completion'))

    def test_two_connection_restart_recovery_cannot_race_delivery(self):
        other = self.race_after_delivery_read(lambda store: store.recover_delivery())
        other.recover_delivery()
        row = other.db.execute('SELECT * FROM outbox').fetchone()
        self.assertEqual(row['state'], 'uncertain')
        self.assertEqual(row['message_id'], 'native_A')
        self.assertIn('A admission', row['detail'])
        before = [tuple(r) for r in other.db.execute('SELECT * FROM changes')]
        other.recover_delivery()
        self.assertEqual(before, [tuple(r) for r in other.db.execute('SELECT * FROM changes')])
        with self.assertRaises(ValueError):
            other.delivery(1, 'admitted', 'replay')
        other.delivery(1, 'completed', detail='native inspected')
        final = tuple(other.db.execute('SELECT * FROM outbox').fetchone())
        other.recover_delivery()
        self.assertEqual(final, tuple(other.db.execute('SELECT * FROM outbox').fetchone()))
        audit = [json.loads(r[0]) for r in other.db.execute("SELECT payload FROM changes WHERE kind='delivery'")]
        self.assertEqual([a['after']['state'] for a in audit], ['admitted', 'uncertain', 'completed'])
        self.assertEqual(audit[-1]['after']['message_id'], 'native_A')

    def test_recovery_inspection_serializes_concurrent_completion(self):
        self.receive()
        self.store.delivery(1, 'admitted', 'native_B', 'B admission')
        other = desk.Store(self.home)
        self.addCleanup(other.close)
        other.db.execute('PRAGMA busy_timeout=0')
        original = self.store.db
        outcomes = []

        class Cursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def fetchall(inner):
                rows = inner.cursor.fetchall()
                try:
                    other.delivery(1, 'completed', detail='B completion')
                    outcomes.append('won')
                except sqlite3.OperationalError:
                    outcomes.append('locked')
                return rows

        class Connection:
            def __enter__(inner):
                original.__enter__()
                return inner

            def __exit__(inner, *args):
                return original.__exit__(*args)

            def execute(inner, sql, *args):
                cursor = original.execute(sql, *args)
                return Cursor(cursor) if sql.startswith("SELECT * FROM outbox WHERE state IN") else cursor

        with patch.object(self.store, 'db', Connection()):
            self.store.recover_delivery()
        self.assertEqual(outcomes, ['locked'])
        other.delivery(1, 'completed', detail='B completion')
        self.store.recover_delivery()
        row = other.db.execute('SELECT * FROM outbox').fetchone()
        self.assertEqual((row['state'], row['message_id']), ('completed', 'native_B'))
        self.assertIn('B admission', row['detail'])
        self.assertIn('B completion', row['detail'])

    def test_delivery_rejects_correlation_replacement_and_rolls_back_audit_failure(self):
        self.receive()
        self.store.delivery(1, 'admitted', 'native_B', 'B evidence')
        with self.assertRaisesRegex(ValueError, 'correlation'):
            self.store.delivery(1, 'completed', 'native_A')
        self.store.db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON changes BEGIN SELECT RAISE(ABORT, 'audit full'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.delivery(1, 'completed', detail='not committed')
        row = self.store.db.execute('SELECT * FROM outbox').fetchone()
        self.assertEqual(row['state'], 'admitted')
        self.assertNotIn('not committed', row['detail'])

    def test_native_trim_crlf_title_and_actual_readback(self):
        self.receive({**self.report, 'landed': '  Done\r\nnext line  '})
        intent = self.store.knowledge_prepare('fixture')
        body = intent['proposed']
        self.assertEqual(body, body.strip())
        self.assertNotIn('\r', body)
        self.assertEqual(body.splitlines()[0], 'fixture — project status')
        self.assertTrue(body.splitlines()[1].startswith('Warning:'))
        self.assertTrue(body.splitlines()[2].startswith('Your part:'))
        self.assertIn('Projected ', body)
        self.store.knowledge_result('fixture', intent['intent'], 'applied', 'native-note', body.strip())
        self.assertEqual(self.store.knowledge_state('fixture')['body'], body)

    def test_utf16_escaped_astral_bound_and_full_source(self):
        landed = '😀[x]' * 1800
        self.receive({**self.report, 'landed': landed})
        intent = self.store.knowledge_prepare('fixture')
        self.assertLessEqual(len(intent['proposed'].encode('utf-16-le')) // 2, 3000)
        self.assertIn('truncated', intent['proposed'])
        self.assertIn('store.sqlite', intent['proposed'])
        self.assertEqual(json.loads(self.store.db.execute('SELECT payload FROM events').fetchone()[0])['landed'], landed)

    def test_exact_native_length_boundary_and_ecmascript_trim(self):
        self.assertEqual(desk.native_note('\ufeff \r\nbody\r\n\ufeff'), 'body')
        self.assertEqual(desk.native_note('\u0085body\u0085'), '\u0085body\u0085')
        self.assertEqual(desk.utf16_units('😀'), 2)
        self.receive({**self.report, 'landed': ''})
        fixed_time = '2026-10-17T00:00:00Z'
        minimum = self.store.knowledge_body('fixture', fixed_time)
        available = 3000 - desk.utf16_units(minimum)
        with patch.object(self.store, 'snapshot', return_value={'watermark': 1, 'projects': {'fixture': {
                **self.store.snapshot()['projects']['fixture'], 'landed': 'x' * available}}}):
            exact = self.store.knowledge_body('fixture', fixed_time)
        self.assertEqual(desk.utf16_units(exact), 3000)
        self.assertNotIn('truncated', exact)
        with patch.object(self.store, 'snapshot', return_value={'watermark': 1, 'projects': {'fixture': {
                **self.store.snapshot()['projects']['fixture'], 'landed': 'x' * (available + 1)}}}):
            over = self.store.knowledge_body('fixture', fixed_time)
        self.assertLessEqual(desk.utf16_units(over), 3000)
        self.assertIn('truncated', over)

    def test_truncated_summary_preserves_entire_wait_and_provenance(self):
        self.receive({**self.report, 'landed': 'x' * 10000, 'next': 'y' * 10000})
        self.store.decision_update('fixture', 1, 'Full principal request 😀 [keep all]', 'chief Q-fixture')
        intent = self.store.knowledge_prepare('fixture')
        self.assertIn('Full principal request 😀 \\[keep all\\]', intent['proposed'])
        self.assertIn('Chief update: chief Q-fixture', intent['proposed'])
        self.assertIn('Ownership: chief-desk-status:fixture', intent['proposed'])
        self.assertLessEqual(desk.utf16_units(intent['proposed']), 3000)

    def test_optional_checkpoint_installed_supplement_and_owner_contract(self):
        supplement = (self.home / 'desk/checkpoint-lead.md').read_text()
        self.assertNotIn('{{', supplement)
        self.assertIn('trusted registry identity update', supplement)
        self.assertIn('file-only claims are not proof', supplement)
        agent = render.owner_values({'mode': 'agent', 'pointer': '/fixture/chief.json', 'label': 'Chief'})
        self.assertNotIn('desk', agent['OWNER'])
        direct = render.lead_prompt({**render.technical_values(str(self.home)),
            **render.owner_values({'mode': 'principal', 'style': 'Short outcomes'})})
        self.assertIn('from the principal that starts with "Goal:"', direct)
        self.assertNotIn('reporting recipient', direct)

    def test_oversized_minimum_pending_no_ack_or_provenance_loss(self):
        receipt = self.receive({**self.report, 'your_part': '😀' * 1600})
        intent = self.store.knowledge_prepare('fixture')
        self.assertEqual(intent['state'], 'pending')
        self.assertNotIn('intent', intent)
        self.assertTrue(self.store.receipt(receipt['seq'])['knowledge_pending'])
        self.assertEqual(self.store.snapshot()['projects']['fixture']['your_part'], '😀' * 1600)

    def test_late_same_text_still_pending_by_watermark(self):
        self.receive()
        first = self.store.knowledge_prepare('fixture')
        self.receive({**self.report, 'id': 'r2', 'source_revision': 2}, {**self.context, 'message_id': 'm2'})
        result = self.store.knowledge_result('fixture', first['intent'], 'applied', 'native-note', first['proposed'])
        self.assertTrue(result['pending_latest'])
        next_intent = self.store.knowledge_prepare('fixture')
        self.assertEqual(next_intent['expected'], first['proposed'])
        self.assertEqual(next_intent['note_id'], 'native-note')

    def test_concurrent_chief_update_cannot_stamp_old_body_with_new_watermark(self):
        self.receive()
        other = desk.Store(self.home)
        self.addCleanup(other.close)
        original = self.store.knowledge_body

        def late_update(project, projected=None, snapshot=None):
            # Chief updates now share the writer guard AND SQLite write lock.
            # The contender must refuse while prepare owns that guard; it may
            # commit after prepare returns, never stamp the older body as newer.
            with self.assertRaises(FileExistsError):
                other.decision_update('fixture', 1, 'New principal wait', 'chief Q-late')
            return original(project, projected, snapshot)

        with patch.object(self.store, 'knowledge_body', side_effect=late_update):
            first = self.store.knowledge_prepare('fixture')
        self.assertEqual(first['watermark'], 1)
        self.assertNotIn('New principal wait', first['proposed'])
        self.assertIsNone(first['todo_intent'])
        other.decision_update('fixture', 1, 'New principal wait', 'chief Q-late')
        result = self.store.knowledge_result('fixture', first['intent'], 'applied', 'native-note', first['proposed'])
        self.assertTrue(result['pending_latest'])
        latest = self.store.knowledge_prepare('fixture')
        self.assertEqual(latest['watermark'], 2)
        self.assertIn('New principal wait', latest['proposed'])
        self.assertEqual(latest['todo_intent']['reference'], 'chief Q-late')
