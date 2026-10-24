import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
import test_api_promo_native as native_fixture
from test_api_promo_native import NOW
from runway.promo import Credit


class CancelTests(unittest.TestCase):
    setUp = native_fixture.NativeTests.setUp
    tearDown = native_fixture.NativeTests.tearDown
    def test_release_and_no_replay(self):
        self.credit.prepare(self.task, NOW)
        self.credit.reserve('other', 12000000, NOW)
        before = self.credit.db.execute('SELECT cycle,bound FROM holds WHERE id=?', ('job-a',)).fetchone()
        self.credit.cancel_unsent('job-a', True)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 12)
        self.assertEqual(self.credit.status(NOW)['spent_usd'], 0)
        self.assertEqual(self.credit.db.execute('SELECT cycle,bound FROM holds WHERE id=?', ('job-a',)).fetchone(), before)
        self.assertEqual(self.credit.db.execute('SELECT actual,receipt FROM holds WHERE id=?', ('job-a',)).fetchone(), (0, None))
        for operation in (lambda: self.credit.cancel_unsent('job-a', True),
                          lambda: self.credit.prepare(self.task, NOW),
                          lambda: self.credit.change('job-a', 'prepared', 'creating')):
            with self.assertRaises(ValueError):
                operation()

    def test_rejections_and_rollback(self):
        self.credit.prepare(self.task, NOW)
        for value in (None, False, 1, 'true'):
            with self.assertRaises(ValueError):
                self.credit.cancel_unsent('job-a', value)
        original = self.credit.job('job-a')
        for update in ({'state': 'creating'}, {'state': 'bound'}, {'state': 'sent'},
                       {'state': 'unknown'}, {'session': None}, {'receipt': 'contradiction'}):
            self.credit.db.execute('UPDATE jobs SET body=?', (json.dumps({**original, **update}),))
            with self.assertRaises(ValueError):
                self.credit.cancel_unsent('job-a', True)
        self.credit.db.execute('UPDATE jobs SET body=?,session=?', (json.dumps(original), 'ses_x'))
        with self.assertRaises(ValueError):
            self.credit.cancel_unsent('job-a', True)
        self.credit.db.execute('UPDATE jobs SET session=NULL')
        self.credit.db.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON jobs BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.credit.cancel_unsent('job-a', True)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 1)
        self.assertEqual(self.credit.job('job-a')['state'], 'prepared')

    def test_create_race(self):
        self.credit.prepare(self.task, NOW)
        barrier = threading.Barrier(2)
        def run(cancel):
            credit = Credit(self.root / 'promo.sqlite3')
            try:
                barrier.wait()
                try:
                    if cancel:
                        credit.cancel_unsent('job-a', True)
                    else:
                        credit.change('job-a', 'prepared', 'creating')
                    return True
                except ValueError:
                    return False
            finally:
                credit.close()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, (True, False)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 0 if results[0] else 1)
