import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runway.policy import timestamp
from runway.ledger import Ledger
from runway.usage import assess
from runway.cli import handle

NOW = 1800000000


def window(wid, remaining, hours, duration=10080):
    return {'id': wid, 'label': wid, 'unit': 'percent', 'remaining_percent': remaining,
            'resets_at': timestamp(NOW + hours * 3600) if hours is not None else None,
            'stale': False, 'duration_minutes': duration}


def source(name, windows, kind='plan'):
    return {'id': name, 'slug': name, 'provider': name, 'account': '', 'enabled': True, 'archived': False,
            'kind': kind, 'needs_login': False,
            'latest': {'observed_at': timestamp(NOW - 10), 'fresh_until': timestamp(NOW + 3600),
                       'reason': None, 'windows': windows}}


def route(name, rid, categories):
    return {'id': rid, 'host': 'local', 'model': f'{name}/{rid}', 'provider': name, 'account': '',
            'source': name, 'pool': name, 'windows': 'all', 'categories': categories, 'max_parallel': 2}


def config():
    return {'version': 1, 'routes': [
        route('gpt', 'gpt-quick', ['trivial', 'research']),
        route('gpt', 'gpt-strong', ['research', 'implement', 'hard']),
        route('claude', 'claude-strong', ['research', 'implement', 'hard'])]}


def snapshot(*sources):
    return {'schema_version': 2, 'passive': True, 'sources': list(sources)}


class AssessTests(unittest.TestCase):
    def test_weekly_allowance_with_plenty_left_near_reset_is_burnable(self):
        r = assess(config(), snapshot(source('gpt', [window('weekly', 60, 9)])), NOW)
        self.assertEqual(r['choice']['route'], 'gpt-strong')
        self.assertEqual(r['choice']['hours_left'], 9.0)

    def test_not_burnable_when_reset_is_days_away_or_little_is_left(self):
        for w in (window('weekly', 90, 72), window('weekly', 15, 6)):
            self.assertIsNone(assess(config(), snapshot(source('gpt', [w])), NOW)['choice'])

    def test_short_window_needs_more_left_and_a_closer_reset(self):
        self.assertIsNotNone(assess(config(), snapshot(source('claude', [window('5h', 70, 1.5, 300)])), NOW)['choice'])
        self.assertIsNone(assess(config(), snapshot(source('claude', [window('5h', 70, 3, 300)])), NOW)['choice'])
        self.assertIsNone(assess(config(), snapshot(source('claude', [window('5h', 30, 1, 300)])), NOW)['choice'])

    def test_another_nearly_empty_window_blocks_the_burn_unless_it_resets_soon(self):
        r = assess(config(), snapshot(source('gpt', [window('weekly', 60, 9), window('5h', 5, 4, 300)])), NOW)
        self.assertIsNone(r['choice'])
        self.assertIn('nearly out', r['skipped'][-1]['reason'])
        r = assess(config(), snapshot(source('gpt', [window('weekly', 60, 9), window('5h', 5, 0.5, 300)])), NOW)
        self.assertIsNotNone(r['choice'])

    def test_unknown_reset_never_burns_but_can_be_low(self):
        r = assess(config(), snapshot(source('claude', [window('5h', 90, None, 300), window('weekly', 4, None)])), NOW)
        self.assertIsNone(r['choice'])
        self.assertEqual([e['window'] for e in r['low']], ['weekly'])

    def test_paid_unrouted_and_stale_sources_are_never_burned(self):
        paid = source('gpt', [window('weekly', 90, 2)], kind='api')
        stale = source('claude', [window('weekly', 90, 2)])
        stale['latest']['fresh_until'] = timestamp(NOW - 1)
        r = assess(config(), snapshot(paid, stale, source('xai', [window('weekly', 90, 2)])), NOW)
        self.assertIsNone(r['choice'])
        self.assertEqual({s['source'] for s in r['skipped']}, {'gpt', 'claude'})

    def test_thresholds_can_be_tuned_in_the_route_registry(self):
        snap = snapshot(source('gpt', [window('weekly', 15, 6)]))
        self.assertIsNotNone(assess(config(), snap, NOW, {'long_burn_percent': 10})['choice'])


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name) / 'l.db'); self.addCleanup(self.ledger.close)
        self.catalog = {'directory': '/repo', 'observed_at': timestamp(NOW), 'models': [
            {'providerID': p, 'id': rid, 'enabled': True, 'status': 'active',
             'capabilities': {'tools': True, 'input': ['text']}, 'variants': [], 'limit': {'context': 1}}
            for p, rid in (('gpt', 'gpt-quick'), ('gpt', 'gpt-strong'), ('claude', 'claude-strong'))]}
        self.task = {'job': 'j', 'scope': '/p', 'directory': '/repo', 'category': 'hard', 'size': 'small'}

    def test_dispatch_prefers_an_allowance_that_would_go_unspent(self):
        # Claude has far more headroom per hour, so without burn mode routing would pick it.
        quiet = snapshot(source('gpt', [window('weekly', 30, 30)]), source('claude', [window('weekly', 95, 2)]))
        self.assertEqual(self.ledger.plan(config(), quiet, self.catalog, self.task, NOW)['selected']['route'], 'claude-strong')
        burn = snapshot(source('gpt', [window('weekly', 30, 20)]), source('claude', [window('weekly', 95, 100)]))
        plan = self.ledger.plan(config(), burn, self.catalog, self.task, NOW)
        self.assertEqual(plan['selected']['route'], 'gpt-strong')
        self.assertTrue(plan['selected']['burning'])
        self.assertIn('Burn mode', plan['selected']['reason'])
        self.assertEqual([b['source'] for b in plan['usage']['burn']], ['gpt'])

    def test_explicit_use_before_reset_still_wins(self):
        snap = snapshot(source('gpt', [window('weekly', 30, 20)]), source('claude', [window('weekly', 95, 100)]))
        self.ledger.prefer(config(), snap, '/p', 'claude-strong', 'weekly', NOW)
        self.assertEqual(self.ledger.plan(config(), snap, self.catalog, self.task, NOW)['selected']['route'], 'claude-strong')

    def test_usage_action_needs_no_host_server(self):
        class Tarmac:
            def get(self, path):
                return snapshot(source('gpt', [window('weekly', 60, 9)]), source('claude', [window('weekly', 5, 50)]))
        with patch('runway.cli.time.time', return_value=NOW):
            text = handle({'action': 'usage'}, config(), self.ledger, Tarmac(), None)
            raw = handle({'action': 'usage', 'format': 'json'}, config(), self.ledger, Tarmac(), None)
        self.assertIn('BURN: use first', text); self.assertIn('LOW: avoid for new work', text)
        self.assertLess(len(text), 1500)
        self.assertEqual([b['source'] for b in raw['burn']], ['gpt'])
        self.assertEqual([e['source'] for e in raw['low']], ['claude'])
        self.assertNotIn('choice', raw)

    def test_paid_sources_show_balance_and_need_permission(self):
        from runway.usage import table
        paid = {'id': 'deepseek', 'slug': 'deepseek', 'kind': 'api', 'enabled': True,
                'latest': {'fresh_until': timestamp(NOW + 3600), 'remaining': 9.65, 'unit': 'USD', 'windows': []}}
        text = table(config(), snapshot(paid, source('gpt', [window('weekly', 60, 9)])), NOW)
        self.assertIn('9.65 USD', text); self.assertIn('PAID: only with permission', text)

    def test_compact_plan_keeps_dispatch_args_and_drops_bulk(self):
        from runway.cli import compact_plan
        snap = snapshot(source('gpt', [window('weekly', 30, 20)]), source('claude', [window('weekly', 95, 100)]))
        full = self.ledger.plan(config(), snap, self.catalog, self.task, NOW, admit=True)
        slim = compact_plan(full)
        self.assertEqual(slim['args'], full['args']); self.assertEqual(slim['action'], full['action'])
        self.assertEqual(slim['attempt']['id'], full['attempt']['id'])
        self.assertNotIn('reservation', slim['attempt']); self.assertNotIn('task', slim['attempt'])
        self.assertTrue(all(isinstance(x, str) for x in slim['alternatives'] + slim['rejected']))
        self.assertLess(len(json.dumps(slim)), len(json.dumps(full)) / 2)
