import concurrent.futures
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runway.promo import Credit, STOP, absent_only, cycle, plan, usage_cost
from runway.cli import handle

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp()
NEXT = datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp()


class PromoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'promo.sqlite3'
        self.c = Credit(self.path)
        self.c.verify_cycle(cycle(NOW)[0], 0)

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_cap_counts_holds(self):
        for i in range(9):
            self.c.reserve(str(i), 20_000_000, NOW)
        with self.assertRaisesRegex(ValueError, '180'):
            self.c.reserve('over', 1, NOW)
        self.assertEqual(self.c.status(NOW)['held_usd'], 180)

    def test_concurrent_admission_atomic(self):
        self.c.close()
        def attempt(i):
            c = Credit(self.path)
            try:
                c.reserve(str(i), 20_000_000, NOW)
                return True
            except ValueError:
                return False
            finally:
                c.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(16)))
        self.c = Credit(self.path)
        self.assertEqual(sum(results), 9)

    def test_idempotent_settlement_and_receipt_uniqueness(self):
        self.c.reserve('a', 100, NOW)
        self.c.settle('a', 'native-message-a', 50)
        self.c.settle('a', 'native-message-a', 50)
        self.assertEqual(self.c.status(NOW)['spent_usd'], .00005)
        with self.assertRaises(ValueError):
            self.c.settle('a', 'native-message-a', 51)
        self.c.reserve('b', 100, NOW)
        with self.assertRaises(Exception):
            self.c.settle('b', 'native-message-a', 50)
        self.assertEqual(self.c.status(NOW)['held_usd'], .0001)

    def test_unknown_usage_retained(self):
        self.c.reserve('a', 100, NOW)
        with self.assertRaises(ValueError):
            self.c.settle('a', 'error', None)
        with self.assertRaises(ValueError):
            usage_cost('claude-opus-5-5', {'input': 0})
        self.assertEqual(self.c.status(NOW)['held_usd'], .0001)

    def test_rollover_requires_verification_carries_unknown(self):
        self.c.reserve('a', 20_000_000, NOW)
        self.assertFalse(self.c.status(NEXT)['cycle_verified'])
        with self.assertRaisesRegex(ValueError, 'unverified'):
            self.c.reserve('b', 1, NEXT)
        self.c.verify_cycle(cycle(NEXT)[0], 170_000_000)
        with self.assertRaisesRegex(ValueError, '180'):
            self.c.reserve('b', 1, NEXT)
        self.assertEqual(self.c.status(NEXT)['held_usd'], 20)

    def test_burn_never_admits_bulk_or_overrides_boundary(self):
        self.assertTrue(self.c.status(NOW)['burn'])
        with self.assertRaises(ValueError):
            plan({'route': 'api-fable', 'purpose': 'bulk', 'prefer': True})
        p = plan({'route': 'api-fable', 'purpose': 'independent-review', 'prefer': True, 'text': 'Review this.'})
        self.assertFalse(p['dispatch_allowed'])
        self.assertEqual(p['selected']['variant'], 'high')
        self.assertFalse(p['subscription_fallback'])

    def test_api_required_cannot_fallback_to_subscription(self):
        with self.assertRaises(ValueError):
            handle({'action': 'prepare', 'task': {'api_required': True}}, {}, None, None, None)

    def test_autonomous_contract_rejected(self):
        for key in ('goal', 'tools', 'warming', 'continue_session'):
            with self.assertRaises(ValueError):
                plan({'route': 'api-opus', 'purpose': 'api-only', key: True})

    def test_duplicate_reservation_not_redispatchable(self):
        self.c.reserve('a', 1, NOW)
        with self.assertRaises(ValueError):
            self.c.reserve('a', 1, NOW)

    def test_bound_breach_stops_future_cycles(self):
        self.c.reserve('a', 1, NOW)
        self.assertTrue(self.c.settle('a', 'a', 2)['bound_exceeded'])
        with self.assertRaisesRegex(ValueError, 'bound exceeded'):
            self.c.reserve('b', 1, NOW)

    def test_official_price_and_cache_upper_bound(self):
        self.assertEqual(usage_cost('claude-fable-5-1', {
            'input': 1000, 'output': 100, 'reasoning': 0,
            'cache': {'read': 1000, 'write': 1000}}), 35250)

    def test_real_fable_receipt_separate_reasoning(self):
        tokens = {'input': 4, 'output': 0, 'reasoning': 2048,
                  'cache': {'write': 10445, 'read': 0}}
        self.assertEqual(usage_cost('claude-fable-5-1', tokens), 311340)
        for bad in (None, -1, True, 1.0, '2048'):
            with self.subTest(reasoning=bad), self.assertRaises(ValueError):
                usage_cost('claude-fable-5-1', {**tokens, 'reasoning': bad})
        del tokens['reasoning']
        with self.assertRaises(ValueError):
            usage_cost('claude-fable-5-1', tokens)

    def test_native_receipt_usage_and_error_retention(self):
        self.c.reserve('a', 1000, NOW)
        m = {'id': 'message-a', 'type': 'assistant', 'finish': 'stop',
             'model': {'providerID': 'anthropic-promo', 'id': 'claude-haiku-5-5'},
             'time': {'completed': NOW}, 'tokens': {'input': 100, 'output': 2,
             'reasoning': 0, 'cache': {'read': 0, 'write': 0}}}
        with self.assertRaises(ValueError):
            self.c.settle_native('a', {**m, 'retry': {'attempt': 1}}, 'claude-haiku-5-5')
        self.assertEqual(self.c.status(NOW)['held_usd'], .001)
        self.c.settle_native('a', m, 'claude-haiku-5-5')
        self.c.settle_native('a', m, 'claude-haiku-5-5')
        self.assertEqual(self.c.status(NOW)['spent_usd'], .000055)

    def test_config_preservation_and_collision(self):
        root = Path(__file__).resolve().parents[1]
        additions = json.loads((root / 'routing/api-promo.opencode.json').read_text())
        old = {'model': 'claude-code/existing', 'warming': True, 'unknown': {'future': 7},
               'providers': {'claude-code': {'opaque': 'preserved'}}, 'policies': [{'keep': True}]}
        before = copy.deepcopy(old)
        result = absent_only(old, additions)
        self.assertEqual(old, before)
        for key in old:
            if key != 'providers':
                self.assertEqual(result[key], old[key])
        self.assertEqual(result['providers']['claude-code'], old['providers']['claude-code'])
        self.assertEqual(result['providers']['anthropic-promo']['settings']['apiKey'],
                         '{file:~/.chief-of-staff/secrets/anthropic-api.key}')
        self.assertNotIn('steps', result['agents']['api-promo-review'])
        with self.assertRaises(ValueError):
            absent_only(result, additions)


if __name__ == '__main__':
    unittest.main()
