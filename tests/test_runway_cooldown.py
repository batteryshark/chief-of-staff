import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_routing import fixture, NOW, timestamp
from runway.cli import LocalAPI, handle, compact_plan
from runway.failure import quota_failure
from runway.ledger import Ledger
from runway.policy import decide, instant


class CooldownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name) / 'db')
        self.addCleanup(self.ledger.close)
        self.config, self.snapshot, self.catalog, self.task = fixture()
        self.task['writer'] = False
        self.a = self.ledger.plan(self.config, self.snapshot, self.catalog, self.task, NOW, admit=True)['attempt']
        self.a = self.ledger.bind(self.a['id'], {'id': 'ses_fixture', 'location': {'directory': '/repo'},
                        'model': {'providerID': 'claude', 'id': 'strong'}}, NOW)

    def report(self, **kw):
        return self.ledger.report_failure(self.a['id'], dict(message='Individual quota reached; resets in about120h', **kw), NOW + 2)

    def plan(self, **kw):
        self.task['job'] += 'x'
        return self.ledger.plan(self.config, self.snapshot, self.catalog,
                                self.task, NOW + 3, **kw)

    def test_high_aggregate_aliases_preference_burn_and_other_models(self):
        for w in self.snapshot['sources'][1]['latest']['windows']:
            w['remaining_percent'] = 99
        alias = {**self.config['routes'][1], 'id': 'alias'}
        quick = {**alias, 'id': 'quick', 'model': 'claude/quick'}
        self.config['routes'] += [alias, quick]
        self.catalog['models'].append({**self.catalog['models'][1], 'id': 'quick'})
        c = self.report()['cooldown']
        self.ledger.prefer(self.config, self.snapshot, '/project', 'claude', '5h', NOW)
        result = self.plan(admit=True)
        self.assertEqual(result['selected']['route'], 'quick')
        self.assertEqual({r['route'] for r in result['rejected']}, {'claude', 'alias'})
        self.assertEqual(instant(c['until']), NOW + 2 + 120 * 3600)
        self.assertIn('cooldown until', compact_plan(result)['rejected'][0])
        forced = decide(self.config, self.snapshot, self.catalog, self.task, [],
                        self.ledger.preference('/project'), NOW+3, burning=['claude'], cooldowns=[c])
        self.assertEqual(forced['selected']['route'], 'quick')

    def test_idempotent_report_survives_restart_without_releasing_ownership(self):
        first = self.report()['cooldown']
        again = self.ledger.report_failure(self.a['id'], {'message': 'Individual quota reached; resets in about120h'}, NOW+999)['cooldown']
        self.assertEqual(first, again)
        self.assertEqual(self.ledger.get(self.a['id'])['state'], 'running')
        self.assertNotIn('usage_released', self.ledger.get(self.a['id']))
        other = Ledger(Path(self.tmp.name) / 'db')
        try:
            self.assertEqual(other.cooldowns(), [first])
        finally:
            other.close()

    def test_richer_hint_anchors_to_original_failure_not_report_clock(self):
        a = self.ledger.report_failure(self.a['id'], dict(message='busy', status=429, key='msg_native'), NOW)
        b = self.ledger.report_failure(self.a['id'], dict(message='Individual quota reached resets in about120h', key='msg_native'), NOW+500)
        self.assertEqual(instant(b['cooldown']['until']), NOW + 432000)
        self.assertEqual(a['cooldown']['observed_at'], b['cooldown']['observed_at'])
        c = self.ledger.report_failure(self.a['id'], dict(message='Individual quota reached resets in about120h', key='msg_native'), NOW+900)
        self.assertEqual(b, c)

    def test_exclusions_next_blocked_malformed_and_no_shared_mutation(self):
        before = copy.deepcopy(self.config)
        result = self.plan(admit=True, exclude_routes=['claude'])
        self.assertEqual(result['selected']['route'], 'gpt')
        self.assertEqual(result['attempt']['exclude_routes'], ['claude'])
        self.assertEqual(result['args']['directory'], '/repo')
        self.assertIsNone(self.plan(exclude_routes=['gpt', 'claude'])['selected'])
        for value in ['claude', [123], ['missing'], {}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(exclude_routes=value)
        self.assertEqual(before, self.config)

    def test_no_exclusion_bypass_cooldown_headroom_or_concurrency(self):
        self.report()
        self.assertIsNone(self.plan(exclude_routes=['gpt'])['selected'])
        self.snapshot['sources'][0]['latest']['windows'][0]['remaining_percent'] = 0
        self.assertIsNone(self.plan(exclude_routes=['claude'])['selected'])
        self.snapshot['sources'][0]['latest']['windows'][0]['remaining_percent'] = 80
        for i in range(2):
            self.assertTrue(self.ledger.plan(self.config, self.snapshot, self.catalog,
                            {**self.task, 'job': str(i)}, NOW+3, admit=True)['dispatch_allowed'])
        self.assertIsNone(self.plan()['selected'])

    def test_native_assistant_shape_only_and_finish_uncertain(self):
        api = LocalAPI('http://127.0.0.1:1234')
        native = dict(id='msg_failed', type='assistant', model={'providerID':'claude','id':'strong'},
                      time={'created': (NOW+1)*1000}, finish='error',
                      error={'type':'ProviderError', 'message':'Individual quota reached resets in 120h', 'status':429})
        api.get = lambda *a, **k: {'data': [native]}
        failure = api.provider_failure(self.a)
        self.assertEqual(failure['key'], 'msg_failed')
        api.idle_evidence = lambda *a, **k: dict(session_id='ses_fixture', idle=True, inbox_empty=True,
                            last_idle_at=timestamp(NOW+2), observed_at=timestamp(NOW+3), outcome='failed')
        with patch('runway.cli.time.time', return_value=NOW+3):
            observed = handle(dict(action='report-failure', attempt=self.a['id']), self.config, self.ledger, None, api)
            self.assertTrue(observed['recorded'])
            self.assertEqual(self.ledger.get(self.a['id'])['state'], 'running')
            with self.assertRaisesRegex(ValueError, 'successful'):
                handle(dict(action='finish', attempt=self.a['id'], state='completed', tools_reconciled=True,
                            effects_reconciled=True), self.config, self.ledger, None, api)
            result = handle(dict(action='finish', attempt=self.a['id'], state='uncertain'), self.config, self.ledger, None, api)
            self.assertTrue(result['failure_observation']['recorded'])
            handle(dict(action='finish', attempt=self.a['id'], state='uncertain'), self.config, self.ledger, None, api)
        self.assertEqual(len(self.ledger.cooldowns()), 1)
        self.assertEqual(self.ledger.get(self.a['id'])['state'], 'uncertain')
        self.assertTrue(self.ledger.get(self.a['id'])['usage_released'])
        for mutation in [dict(type='tool'), dict(finish='stop'), dict(model={'providerID':'gpt','id':'strong'}),
                         dict(time={'created': (NOW-1)*1000}), dict(error=None)]:
            api.get = lambda *a, **k: {'data': [{**native, **mutation}]}
            self.assertIsNone(api.provider_failure(self.a))

    def test_native_response_body_reset_hint(self):
        api = LocalAPI('http://127.0.0.1:1234')
        api.get = lambda *a, **k: {'data': [dict(id='msg_body', type='assistant',
                 model={'providerID':'claude','id':'strong'}, time={'created':(NOW+1)*1000}, finish='error',
                 error={'type':'ProviderError', 'message':'HTTP 429', 'status':429,
                        'response':{'body':'{"error":"Individual quota reached; resets in ~120h"}'}})]}
        f = api.provider_failure(self.a)
        c = self.ledger.report_failure(self.a['id'], f, NOW+2)['cooldown']
        self.assertEqual(instant(c['until']), NOW+1+432000)
        self.assertNotIn('message', c)

    def test_host_http_error_is_not_provider_failure(self):
        from urllib.error import HTTPError
        api = LocalAPI('http://127.0.0.1:1234')
        def unavailable(*a, **k):
            raise HTTPError('http://localhost/api/session/x/inbox', 429, 'quota exceeded', {}, None)
        api.get = unavailable
        with patch('runway.cli.time.time', return_value=NOW+3):
            handle(dict(action='finish', attempt=self.a['id'], state='uncertain'), self.config, self.ledger, None, api)
        self.assertEqual(self.ledger.cooldowns(), [])
        self.assertFalse(self.ledger.get(self.a['id'])['usage_released'])

    def test_unbound_report_and_unrelated_error(self):
        self.assertIsNone(quota_failure(dict(message='directory lookup HTTPError 500'), NOW))
        a = self.ledger.plan(self.config, self.snapshot, self.catalog, {**self.task, 'job':'unbound'}, NOW, admit=True)['attempt']
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.ledger.report_failure(a['id'], dict(message='quota exceeded'), NOW)

    def test_reset_retry_after_and_expiry(self):
        for f, seconds in [({'message':'quota exceeded resets in120h'},432000),
                           ({'message':'quota exceeded resets in about 120h'},432000),
                           ({'message':'Individual quota reached resets in ~120h'},432000),
                           ({'message':'busy','status':429,'retry_after':60},60),
                           ({'message':'busy','status':429},300),
                           ({'message':'rate limit', 'reset_at':timestamp(NOW+90)},90),
                           ({'message':'rate limit', 'retry_after':'Fri, 15 Jan 2027 08:01:00 GMT'},60),
                           ({'message':'429 Retry-After: 45','status':429},45)]:
            # HTTP-date uses its own fixed clock rather than NOW fixture's date.
            clock = instant('2027-01-15T08:00:00Z') if isinstance(f.get('retry_after'), str) else NOW
            c = quota_failure(f, clock)
            self.assertEqual(instant(c['until']) - clock, seconds)
        c = self.ledger.report_failure(self.a['id'], dict(message='busy', status=429, retry_after=1), NOW)['cooldown']
        self.assertEqual(self.plan()['selected']['route'], 'claude')


if __name__ == '__main__':
    unittest.main()
