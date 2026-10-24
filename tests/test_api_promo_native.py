import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runway.promo import Credit, cycle
from runway.promo_install import install, rollback, splice, JSONC
from runway.promo_native import Native, dispatch, collect, bind, claim_send, create_body, same_model, validate_session
from runway.cli import main

NOW = 1792713600  # 2026-10-23 UTC
SOURCE = Path(__file__).resolve().parents[1]
POLICY = {'grant_micro_usd': 200_000_000, 'renewal_day': 26}  # synthetic fixture


def authority():
    return {'console_backstop': True, 'exclusive_key': True, 'reference': 'fixture-approval',
            'baseline_micro_usd': 0, 'verified_cycle': cycle(NOW, 26)[0]}


class FakeNative:
    def __init__(self):
        self.info = {}
        self.messages = []
        self.prompts = 0
        self.failure = False
        self.active = False
        self.receipt = None

    def call(self, method, path, body=None):
        if path == '/api/session':
            self.info = {**body, 'id': 'ses_fixture'}
            return {'data': self.info}
        if path.endswith('/prompt'):
            self.prompts += 1
            if self.failure:
                raise ValueError('fixture transport uncertainty')
            self.messages = [{'type': 'user', 'id': 'user-a', **body}]
            return {'data': {'id': 'inbox-a'}}
        return self.get(path)

    def get(self, path):
        if path == '/api/session/active':
            return {'data': {'ses_fixture': {}} if self.active else {}}
        if '/message?' in path:
            messages = self.messages + ([self.receipt] if self.receipt else [])
            return {'data': messages, 'cursor': {'next': None, 'previous': None}}
        if path.endswith(('/inbox', '/permission', '/form')):
            return {'data': []}
        return {'data': self.info}

    def complete(self):
        self.receipt = {'id': 'assistant-a', 'type': 'assistant', 'finish': 'stop',
                        'model': self.info['model'], 'agent': 'api-promo-review',
                        'time': {'completed': NOW}, 'content': [{'type': 'text', 'text': 'OK'}],
                        'tokens': {'input': 100, 'output': 2, 'reasoning': 0,
                                   'cache': {'read': 0, 'write': 0}}}


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'promo-policy.json').write_text(json.dumps(POLICY))
        self.credit = Credit(self.root / 'promo.sqlite3')
        self.credit.authorize(NOW, authority())
        self.task = {'attempt': 'job-a', 'route': 'api-haiku-proof', 'purpose': 'proof',
                     'directory': str(self.root.resolve()), 'text': 'Reply OK only.'}
        self.native = FakeNative()

    def tearDown(self):
        self.credit.close()
        self.tmp.cleanup()

    def test_prepare_dispatch_and_idempotent_native_settlement(self):
        prepared = self.credit.prepare(self.task, NOW)
        self.assertTrue(prepared['dispatch_allowed'])
        self.assertEqual(prepared['native_create']['body']['model']['id'], 'claude-haiku-5-5')
        self.assertEqual(self.credit.status(NOW)['held_usd'], 1)
        sent = dispatch(self.credit, 'job-a', self.task['text'], self.native, NOW)
        self.assertEqual(sent['state'], 'sent')
        self.assertEqual(collect(self.credit, 'job-a', self.native)['state'], 'pending')
        self.native.complete()
        result = collect(self.credit, 'job-a', self.native)
        self.assertEqual(result['observed_micro_usd'], 55)
        self.assertEqual(result['receipts'][0]['tokens']['input'], 100)
        self.assertEqual(result['text'], 'OK')
        self.assertEqual(collect(self.credit, 'job-a', self.native), result)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 0)
        self.assertEqual(self.credit.status(NOW)['spent_usd'], .000055)
        self.assertEqual(self.native.prompts, 1)
        with self.assertRaises(ValueError):
            dispatch(self.credit, 'job-a', self.task['text'], self.native, NOW)

    def test_prepare_requires_console_backstop(self):
        self.credit.db.execute('DELETE FROM authority')
        with self.assertRaises(ValueError):
            self.credit.prepare(self.task, NOW)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 0)

    def test_practical_reservation_and_cap(self):
        for i in range(15):
            self.credit.prepare({**self.task, 'attempt': str(i), 'route': 'api-fable',
                                 'purpose': 'independent-review'}, NOW)
        with self.assertRaises(ValueError):
            self.credit.prepare(self.task, NOW)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 180)

    def test_unknown_send_never_automatically_retried(self):
        self.credit.prepare(self.task, NOW)
        self.native.failure = True
        with self.assertRaises(ValueError):
            dispatch(self.credit, 'job-a', self.task['text'], self.native, NOW)
        with self.assertRaises(ValueError):
            dispatch(self.credit, 'job-a', self.task['text'], self.native, NOW)
        self.assertEqual(self.native.prompts, 1)
        self.assertEqual(self.credit.job('job-a')['state'], 'sent')
        self.assertEqual(self.credit.status(NOW)['held_usd'], 1)

    def test_external_native_create_bind_claim_path(self):
        p = self.credit.prepare(self.task, NOW)
        self.native.call('post', p['native_create']['path'], p['native_create']['body'])
        self.native.info['model'] = {**self.native.info['model'], 'variant': 'default'}
        bind(self.credit, 'job-a', 'ses_fixture', self.native)
        request = claim_send(self.credit, 'job-a', self.task['text'], self.native, NOW)
        self.assertEqual(self.native.prompts, 0)
        with self.assertRaises(ValueError):
            claim_send(self.credit, 'job-a', self.task['text'], self.native, NOW)
        self.native.call('post', request['native_prompt']['path'], request['native_prompt']['body'])
        self.native.complete()
        self.assertEqual(collect(self.credit, 'job-a', self.native)['state'], 'settled')

    def test_same_model_only_normalizes_missing_default_variant(self):
        model = {'id': 'claude-haiku-5-5', 'providerID': 'anthropic-promo'}
        default = {**model, 'variant': 'default'}
        for left, right in ((model, model), (model, default), (default, model), (default, default)):
            self.assertTrue(same_model(left, right))
        for other in (None, {}, {**model, 'variant': None}, {**model, 'variant': ''},
                      {**model, 'variant': 'high'}, {**model, 'variant': 'medium'},
                      {**model, 'id': 'claude-opus-5-5'}, {**model, 'providerID': 'claude-code'},
                      {**model, 'extra': 'unexpected'}):
            self.assertFalse(same_model(other, model))
            self.assertFalse(same_model(model, other))
        self.assertFalse(same_model({**model, 'extra': True}, {**model, 'extra': True}))

    def test_fable_high_remains_strict_in_session_and_receipt(self):
        task = {**self.task, 'route': 'api-fable', 'purpose': 'independent-review'}
        self.credit.prepare(task, NOW)
        dispatch(self.credit, 'job-a', task['text'], self.native, NOW)
        job = {**self.credit.job('job-a'), 'attempt': 'job-a'}
        validate_session(job, self.native.info)
        self.native.complete()
        for variant in (None, 'default', 'medium'):
            wrong = {k: v for k, v in self.native.info['model'].items() if k != 'variant'}
            if variant is not None:
                wrong['variant'] = variant
            with self.assertRaises(ValueError):
                validate_session(job, {**self.native.info, 'model': wrong})
            self.native.receipt['model'] = wrong
            with self.assertRaises(ValueError):
                collect(self.credit, 'job-a', self.native)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 12)
        self.native.receipt['model'] = self.native.info['model']
        self.assertEqual(collect(self.credit, 'job-a', self.native)['state'], 'settled')

    def test_wrong_caller_error_unknown_usage_keeps_reserve(self):
        self.credit.prepare(self.task, NOW)
        dispatch(self.credit, 'job-a', self.task['text'], self.native, NOW)
        self.native.complete()
        for change in ({'error': {'message': 'private response'}}, {'tokens': {}},
                       {'retry': {'attempt': 1}}, {'model': {'providerID': 'claude-code', 'id': 'other'}}):
            old = self.native.receipt
            self.native.receipt = {**old, **change}
            with self.assertRaises(ValueError):
                collect(self.credit, 'job-a', self.native)
            self.native.receipt = old
        self.native.messages[0]['metadata'] = {'promo_attempt': 'someone-else'}
        with self.assertRaises(ValueError):
            collect(self.credit, 'job-a', self.native)
        self.assertEqual(self.credit.status(NOW)['held_usd'], 1)

    def test_renewal_not_automatically_authorized(self):
        with self.assertRaises(ValueError):
            self.credit.prepare(self.task, NOW + 4 * 86400)

    def test_cli_and_native_errors_never_dump_secrets(self):
        secret = 'private-auth-response-sentinel'
        with patch('runway.promo_native.subprocess.run', return_value=subprocess.CompletedProcess([], 1, secret, secret)):
            with self.assertRaises(ValueError) as error:
                Native().get('/api/session/active')
            self.assertNotIn(secret, str(error.exception))
        config = self.root / 'routes.json'
        config.write_text(json.dumps({'version': 1, 'routes': []}))
        with patch('sys.argv', ['runway', '--home', str(self.root)]), \
             patch('sys.stdin', io.StringIO('{"action":"promo-status"}')), \
             patch('runway.promo.Credit.status', side_effect=ValueError(secret)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertNotIn(secret, output.getvalue())


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'promo-policy.json').write_text(json.dumps(POLICY))
        (self.root / 'promo-opencode.json').write_text((SOURCE / 'routing/api-promo.opencode.json').read_text())
        (self.root / 'promo-routes.json').write_text((SOURCE / 'routing/api-promo.routes.json').read_text())
        self.config = self.root / 'opencode.jsonc'
        self.original = '// untouched\n{\n "unknown": {"literal":"//not a comment"},\n "model":"claude-code/existing",\n "providers": { /* keep */ "claude-code": {"opaque":7}, },\n "agents": {}, "policies":[{"keep":true}],\n}\n'
        self.config.write_text(self.original)
        self.routes = self.root / 'routes.json'
        self.routes.write_text('{"version":1,"routes":[],"unknown":true}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_jsonc_absent_only_roundtrip_and_authority(self):
        dry = install(SOURCE, self.config, self.root, authority(), now=NOW)
        self.assertTrue(dry['dry_run'])
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse((self.root / 'promo.sqlite3').exists())
        result = install(SOURCE, self.config, self.root, authority(), apply=True, now=NOW)
        self.assertTrue(result['dispatch_ready'])
        parsed = JSONC(self.config.read_text()).value
        before = JSONC(self.original).value
        for k in ('unknown', 'model', 'policies'):
            self.assertEqual(parsed[k], before[k])
        self.assertEqual(parsed['providers']['claude-code'], before['providers']['claude-code'])
        self.assertIn('/* keep */', self.config.read_text())
        c = Credit(self.root / 'promo.sqlite3', POLICY)
        c.prepare({'attempt': 'a', 'route': 'api-opus', 'purpose': 'api-only',
                   'directory': str(self.root), 'text': 'Review'}, NOW)
        c.close()
        rollback(self.root)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertEqual(self.routes.read_text(), '{"version":1,"routes":[],"unknown":true}\n')
        c = Credit(self.root / 'promo.sqlite3', POLICY)
        self.assertEqual(c.status(NOW)['held_usd'], 6)
        with self.assertRaises(ValueError):
            c.require_authority(NOW)
        c.close()

    def test_collision_and_missing_backstop_no_effects(self):
        with self.assertRaises(ValueError):
            install(SOURCE, self.config, self.root, {**authority(), 'console_backstop': False}, True, NOW)
        self.assertFalse((self.root / 'promo.sqlite3').exists())
        self.config.write_text('{"providers":{"anthropic-promo":{}}}')
        with self.assertRaises(ValueError):
            install(SOURCE, self.config, self.root, authority(), True, NOW)
        self.assertEqual(self.config.read_text(), '{"providers":{"anthropic-promo":{}}}')

    def test_rollback_refuses_unrelated_edits(self):
        install(SOURCE, self.config, self.root, authority(), True, NOW)
        self.config.write_text(self.config.read_text() + '// new foreign work\n')
        after = self.config.read_text()
        with self.assertRaises(ValueError):
            rollback(self.root)
        self.assertEqual(self.config.read_text(), after)

    def test_jsonc_duplicates_invalid_and_strings(self):
        for text in ('{"a":1,"a":2}', '{"a":}', '{ /* unterminated', '{"a": 1} trailing'):
            with self.assertRaises(ValueError):
                JSONC(text)
        after, edits = splice('{"keep":"{ /* // \\"",}', {'new': {'value': 1}})
        self.assertEqual(JSONC(after).value['new'], {'value': 1})


if __name__ == '__main__':
    unittest.main()
