"""Finite Chief continuation fixtures: no real cards, hosts, credentials or delivery."""
import argparse
import importlib.util
import json
import io
from contextlib import redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC / 'scripts'))
import render
from test_chief_nod import valid_card


class ContinuationTest(unittest.TestCase):
    def test_attention_decoration_never_invents_approval_option_or_recommendation(self):
        request = {'title':'Project review', 'summary':'Review, not authority.', 'notes':False,
                   'default':'No answer grants no approval.', 'options':[
                       {'id':'discuss','label':'Review / discuss','kind':'custom','requires_text':True},
                       {'id':'defer','label':'Not now','kind':'custom'},
                       {'id':'other','label':'Other note','kind':'custom'}]}
        self.nod.card(request)
        self.assertEqual(len(request['options']),3)
        self.assertTrue(all(o['kind']=='custom' for o in request['options']))
        self.assertNotIn('I recommend:',request['body_markdown'])
        self.assertFalse(any(o['id']=='something-else' for o in request['options']))
        self.assertNotIn('notes',request)

    def test_private_decision_json_is_exact_read_only_and_identity_checked(self):
        self.register()
        before = self.read()
        with patch.object(self.nod, 'call', return_value=self.answer) as call:
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(self.nod.decision_json(argparse.Namespace(request_id='r1')), 0)
            self.assertEqual(json.loads(out.getvalue()), self.answer)
            call.assert_called_once_with('GET', '/api/v1/requests/r1/decision')
        self.assertEqual(self.read(), before)
        with patch.object(self.nod, 'call', return_value={'request_id': 'wrong'}):
            with self.assertRaises(ValueError): self.nod.decision_json(argparse.Namespace(request_id='r1'))

    def test_new_bus_ids_never_enter_legacy_delivery(self):
        self.register()
        with self.nod.state() as (data, save):
            with patch.object(self.nod.subprocess, 'run') as run:
                self.nod.deliver(data, save, excluded=['r1'])
                run.assert_not_called()
        self.assertEqual(self.event()[1]['state'], 'ready')

    def test_existing_finite_runner_opts_in_without_legacy_bus_relay(self):
        args = argparse.Namespace(cmd='run', seconds=1, deliver=True, heartbeat_options='/explicit/options.json')
        with patch.object(self.nod.time, 'monotonic', side_effect=[0, 0, 2, 2]):
            with patch.object(self.nod, 'heartbeat_pass', return_value=['r1']) as feed:
                with patch.object(self.nod, 'reconcile') as reconcile:
                    with patch.object(self.nod, 'deliver') as deliver:
                        self.nod.continuation(args)
        feed.assert_called_once_with('/explicit/options.json')
        self.assertEqual(reconcile.call_args.args[2], [])
        self.assertEqual(deliver.call_args.args[2], ['r1'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        script = root / 'chief_nod.py'
        script.write_text(render.render('scripts/chief-nod', '/fixture/chief'))
        spec = importlib.util.spec_from_file_location('nod_fixture', script)
        self.nod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.nod)
        self.home = root / 'state'
        self.pointer = root / 'chief.json'
        self.pointer.write_text(json.dumps({'session': 'ses_ops1', 'directory': '/ops1'}))
        self.env = patch.dict(os.environ, {'CHIEF_NOD_STATE_DIR': str(self.home),
                                          'CHIEF_NOD_OPS_POINTER': str(self.pointer)})
        self.env.start()
        self.origin = {'session': 'ses_original', 'directory': '/original', 'reference': 'private-ref',
                       'limits': 'One hands action only; expires 2000-01-01. Never reboot. No renewed consent.'}
        self.snapshot = {'id': 'r1', 'title': 'Original hands request', 'expires_at': '2000-01-01T00:00:00Z',
                         'options': [{'id': 'done', 'label': 'Signed back in'}]}
        self.answer = {'request_id': 'r1', 'status': 'resolved', 'request_digest': 'digest-1',
                       'decision': {'id': 'a1', 'option_id': 'done', 'text': 'actually signed back in',
                                    'created_at': '2026-10-21T10:00:00Z'}, 'decisions': []}
        self.calls = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def fetch(self, method, path, *args, **kwargs):
        self.calls.append((method, path))
        return self.answer if path.endswith('/decision') else {'request': self.snapshot}

    def register(self, handled=None):
        with self.nod.state() as (data, save):
            self.nod.register_local(data, 'r1', self.origin, handled)
            save()
            with patch.object(self.nod, 'call', side_effect=self.fetch):
                self.nod.reconcile(data, save, ['r1'])

    def read(self):
        return json.loads((self.home / 'state.json').read_text())

    def event(self):
        return next(iter(self.read()['requests']['r1']['events'].items()))

    def deliver(self, side_effect=None, code=0, preflight=None):
        send = Mock(side_effect=side_effect, return_value=argparse.Namespace(returncode=code))
        def invoke(argv, **kwargs):
            if argv[2] == 'status':
                if preflight:
                    return preflight(argv, **kwargs)
                return argparse.Namespace(returncode=0, stdout=json.dumps({
                    'status': 'ok', 'sessionId': argv[argv.index('--session') + 1],
                    'directory': argv[argv.index('--dir') + 1], 'sessionStatus': {'type': 'idle'}}))
            return send(argv, **kwargs)
        with self.nod.state() as (data, save):
            with patch.object(self.nod.shutil, 'which', return_value='/fake/chief-openchamber'):
                with patch.object(self.nod.subprocess, 'run', side_effect=invoke):
                    self.nod.deliver(data, save)
                    return send

    def make_due(self):
        with self.nod.state() as (data, save):
            next(iter(data['requests']['r1']['events'].values()))['next_attempt'] = 0
            save()

    def test_native_outage_then_restart_recovery_never_sends_before_status_recovers(self):
        self.register()
        def offline(argv, **kwargs):
            self.assertEqual(argv[1:3], ['session', 'status'])
            self.assertEqual(kwargs['timeout'], 15)
            self.assertEqual(self.event()[1]['state'], 'ready')
            return argparse.Namespace(returncode=1, stdout='')
        self.assertFalse(self.deliver(preflight=offline).called)
        self.assertEqual(self.event()[1]['state'], 'ready')
        self.assertGreater(self.event()[1]['next_attempt'], self.nod.time.time())
        with self.nod.state():  # Reopen persisted state as after a runner restart.
            pass
        self.assertFalse(self.deliver().called)  # Backoff persists across restart.
        self.make_due()
        self.assertEqual(self.deliver().call_count, 1)
        self.assertEqual(self.event()[1]['state'], 'sent')

    def test_status_timeout_invalid_json_or_wrong_binding_stays_ready(self):
        self.register()
        for result in (subprocess.TimeoutExpired('status', 15),
                       argparse.Namespace(returncode=0, stdout='bad JSON'),
                       argparse.Namespace(returncode=0, stdout='{}'),
                       argparse.Namespace(returncode=0, stdout=json.dumps({
                           'status': 'ok', 'sessionId': 'ses_other', 'directory': '/ops1',
                           'sessionStatus': {'type': 'idle'}}))):
            self.make_due()
            def probe(argv, **kwargs):
                if isinstance(result, Exception):
                    raise result
                return result
            self.assertFalse(self.deliver(preflight=probe).called)
            self.assertEqual(self.event()[1]['state'], 'ready')

    def test_pointer_rotation_during_status_requires_fresh_preflight(self):
        self.register()
        def rotate(argv, **kwargs):
            self.pointer.write_text(json.dumps({'session': 'ses_ops2', 'directory': '/ops2'}))
            return argparse.Namespace(returncode=0, stdout=json.dumps({
                'status': 'ok', 'sessionId': 'ses_ops1', 'directory': '/ops1',
                'sessionStatus': {'type': 'idle'}}))
        self.assertFalse(self.deliver(preflight=rotate).called)
        self.assertEqual(self.event()[1]['state'], 'ready')
        self.make_due()
        run = self.deliver()
        self.assertIn('ses_ops2', run.call_args.args[0])

    def test_busy_native_status_does_not_gate_send_on_idle(self):
        self.register()
        def busy(argv, **kwargs):
            return argparse.Namespace(returncode=0, stdout=json.dumps({
                'status': 'ok', 'sessionId': 'ses_ops1', 'directory': '/ops1',
                'sessionStatus': {'type': 'busy'}}))
        self.assertTrue(self.deliver(preflight=busy).called)

    def operation(self, cmd, **kw):
        eid, _ = self.event()
        args = argparse.Namespace(cmd=cmd, request_id='r1', event_id=eid, reference='private-ref',
                                  receipt='durable-record-1', **kw)
        with patch('builtins.print'):
            return self.nod.continuation(args)

    def test_registration_closes_answer_race_and_persists_private_snapshot(self):
        self.register()
        self.assertEqual(self.calls, [('GET', '/api/v1/requests/r1'), ('GET', '/api/v1/requests/r1/decision')])
        row = self.read()['requests']['r1']
        self.assertEqual(row['origin'], self.origin)
        self.assertEqual(row['snapshot'], self.snapshot)
        self.assertEqual(self.event()[1]['answer'], self.answer)
        self.assertEqual((self.home / 'state.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o700)

    def test_duplicate_observation_does_not_create_another_event(self):
        self.register()
        self.register()
        self.assertEqual(len(self.read()['requests']['r1']['events']), 1)

    def test_canonical_pending_with_per_recipient_answer_is_not_lost(self):
        chosen = self.answer.pop('decision')
        self.answer.update(status='pending', decisions=[chosen])
        self.register()
        self.assertEqual(self.event()[1]['answer']['status'], 'pending')
        self.answer.update(status='resolved', decision=chosen)
        self.register()
        self.assertEqual(len(self.read()['requests']['r1']['events']), 2)

    def test_cancelled_expired_pending_without_answer_do_not_wake(self):
        for status in ('cancelled', 'expired', 'pending'):
            self.answer.update(status=status, decision=None, decisions=[])
            self.register()
            self.assertEqual(self.read()['requests']['r1']['events'], {})

    def test_fetch_outage_retains_answer_and_backs_off(self):
        self.register()
        with self.nod.state() as (data, save):
            with patch.object(self.nod, 'call', side_effect=SystemExit('secret body')):
                self.nod.reconcile(data, save, ['r1'])
        row = self.read()['requests']['r1']
        self.assertEqual(len(row['events']), 1)
        self.assertGreater(row['next_check'], self.nod.time.time())
        self.assertNotIn('secret body', json.dumps(row))

    def test_outage_during_register_still_saves_original_binding(self):
        args = argparse.Namespace(cmd='register', request_id='r1', origin_session='ses_original',
                                  origin_directory='/original', reference='private-ref', limits='hands only',
                                  already_handled=None)
        with patch.object(self.nod, 'call', side_effect=SystemExit('offline')), patch('builtins.print'):
            self.nod.continuation(args)
        self.assertEqual(self.read()['requests']['r1']['origin']['session'], 'ses_original')
        self.assertTrue(self.read()['requests']['r1']['fetch_error'])

    def test_already_relayed_registration_checks_actual_state_but_never_redelivers(self):
        self.register('Ops explicitly confirms previous original-owner relay')
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(self.read()['requests']['r1']['events'])
        self.assertFalse(self.deliver().called)

    def test_rebinding_original_owner_refused(self):
        self.register()
        self.origin['session'] = 'ses_different'
        with self.assertRaises(ValueError):
            self.register()

    def test_live_pointer_changes_between_new_deliveries_not_original_binding(self):
        self.register()
        run = self.deliver()
        self.assertIn('ses_ops1', run.call_args.args[0])
        self.pointer.write_text(json.dumps({'session': 'ses_ops2', 'directory': '/ops2'}))
        self.answer['decision']['text'] = 'new authoritative answer'
        self.register()
        run = self.deliver()
        self.assertEqual(run.call_count, 1)
        self.assertIn('ses_ops2', run.call_args.args[0])
        self.assertEqual(self.read()['requests']['r1']['origin']['session'], 'ses_original')

    def test_quiet_missing_invalid_pointer_never_spawns(self):
        self.register()
        for pointer in ({'session': self.nod.QUIET_CHIEF, 'directory': '/quiet'},
                        {'session': 'ses_ops', 'directory': 'relative'}, {}):
            self.pointer.write_text(json.dumps(pointer))
            with self.nod.state() as (data, save):
                next(iter(data['requests']['r1']['events'].values()))['next_attempt'] = 0
                save()
            self.assertFalse(self.deliver().called)

    def test_durable_send_intent_precedes_process_and_stale_limits_survive(self):
        self.register()
        def inspect(argv, **kwargs):
            self.assertEqual(self.event()[1]['state'], 'sending')
            prompt = argv[argv.index('--prompt') + 1]
            self.assertIn(self.origin['limits'], prompt)
            self.assertIn('2000-01-01T00:00:00Z', prompt)
            self.assertIn('not canonical approval', prompt)
            self.assertIn('2026-10-21T10:00:00Z', prompt)
            self.assertEqual(kwargs['timeout'], 30)
            return argparse.Namespace(returncode=0)
        self.deliver(side_effect=inspect)
        self.assertEqual(self.event()[1]['state'], 'sent')
        self.assertFalse(self.deliver().called)

    def test_timeout_and_failed_cli_are_uncertain_never_retried(self):
        self.register()
        self.deliver(side_effect=subprocess.TimeoutExpired('fake', 30))
        self.assertEqual(self.event()[1]['state'], 'uncertain')
        self.assertFalse(self.deliver().called)
        self.operation('resolve', outcome='not-dispatched')
        self.deliver(code=1)
        self.assertEqual(self.event()[1]['state'], 'uncertain')

    def test_known_pre_dispatch_failure_is_retryable(self):
        self.register()
        self.deliver(side_effect=FileNotFoundError())
        self.assertEqual(self.event()[1]['state'], 'ready')

    def test_restart_sending_is_uncertain_status_not_a_resend(self):
        self.register()
        with self.nod.state() as (data, save):
            next(iter(data['requests']['r1']['events'].values()))['state'] = 'sending'
            save()
        with self.nod.state():
            pass
        self.assertEqual(self.event()[1]['state'], 'uncertain')
        self.assertFalse(self.deliver().called)

    def test_ops_ack_and_actual_owner_handling_are_distinct(self):
        self.register()
        self.deliver(code=1)
        self.operation('ack')
        self.assertEqual(self.event()[1]['state'], 'acknowledged')
        self.operation('handled')
        self.assertEqual(self.event()[1]['state'], 'handled')
        self.assertFalse(self.deliver().called)

    def test_wrong_ack_reference_refused(self):
        self.register()
        self.deliver()
        eid, _ = self.event()
        args = argparse.Namespace(cmd='ack', request_id='r1', event_id=eid, reference='wrong', receipt='record')
        with self.assertRaises(ValueError):
            self.nod.continuation(args)
        self.assertEqual(self.event()[1]['state'], 'sent')

    def test_tracked_ask_registers_with_server_idempotency_and_never_reposts(self):
        args = argparse.Namespace(file=None, channel='chief', image=None, recommended=None, recommendation=None,
                                  dry_run=False, origin_session='ses_original', origin_directory='/original',
                                  reference='private-ref', limits='hands only')
        payload = dict(valid_card(), idempotency_key='stable-create-1')
        def server(method, path, *a, **kw):
            if method == 'POST':
                return {'request_id': 'r1'}
            return self.fetch(method, path)
        with patch.object(self.nod, 'decision_sender', return_value={'session':'ses_original','directory':'/original'}), patch.object(self.nod, 'native_origin', return_value={'session':'ses_original','directory':'/original'}), patch.object(self.nod, 'call', side_effect=server) as call, patch('builtins.print'):
            with patch.object(self.nod.sys, 'stdin', __import__('io').StringIO(json.dumps(payload))):
                self.nod.ask(args)
            self.assertEqual(call.call_count, 3)
            with patch.object(self.nod.sys, 'stdin', __import__('io').StringIO(json.dumps(payload))):
                with self.assertRaises(ValueError):
                    self.nod.ask(args)
            self.assertEqual(call.call_count, 3)
        self.assertEqual(self.read()['creates']['stable-create-1']['request_id'], 'r1')

    def test_lost_create_response_does_not_lose_binding_intent_or_retry_post(self):
        args = argparse.Namespace(file=None, channel='chief', image=None, recommended=None, recommendation=None,
                                  dry_run=False, origin_session='ses_original', origin_directory='/original',
                                  reference='private-ref', limits='hands only')
        payload = json.dumps(dict(valid_card(), idempotency_key='stable-create-1'))
        with patch.object(self.nod, 'decision_sender', return_value={'session':'ses_original','directory':'/original'}), patch.object(self.nod, 'native_origin', return_value={'session':'ses_original','directory':'/original'}), patch.object(self.nod, 'call', side_effect=SystemExit('offline')) as call:
            with patch.object(self.nod.sys, 'stdin', __import__('io').StringIO(payload)):
                with self.assertRaises(SystemExit):
                    self.nod.ask(args)
            with patch.object(self.nod.sys, 'stdin', __import__('io').StringIO(payload)):
                with self.assertRaises(ValueError):
                    self.nod.ask(args)
            self.assertEqual(call.call_count, 1)
        self.assertEqual(self.read()['creates']['stable-create-1']['state'], 'possible-create')

    def test_finite_runner_defaults_to_no_delivery_and_uses_due_backoff(self):
        self.register()
        args = argparse.Namespace(cmd='run', seconds=1, deliver=False)
        with patch.object(self.nod.time, 'monotonic', side_effect=[0, 0, 2, 2]):
            with patch.object(self.nod, 'call') as fetch, patch.object(self.nod, 'deliver') as send:
                self.nod.continuation(args)
        self.assertFalse(send.called)
        self.assertFalse(fetch.called)  # Registered request not due yet.

    def test_runner_heartbeat_advances_when_all_requests_are_handled(self):
        self.register('actual previous relay provenance')
        args = argparse.Namespace(cmd='run', seconds=1, deliver=True)
        with patch.object(self.nod.time, 'monotonic', side_effect=[0, 0, 2, 2]):
            with patch.object(self.nod, 'stamp', return_value='2026-10-21T16:00:00+00:00'):
                with patch.object(self.nod, 'call') as fetch, patch.object(self.nod.subprocess, 'run') as send:
                    self.nod.continuation(args)
        self.assertEqual(self.read()['runner_last_tick'], '2026-10-21T16:00:00+00:00')
        self.assertEqual(self.read()['requests']['r1']['events'], {})
        self.assertFalse(fetch.called)
        self.assertFalse(send.called)

    def test_status_omits_answer_snapshot_and_limits(self):
        self.register()
        with patch('builtins.print') as out:
            self.nod.continuation(argparse.Namespace(cmd='status'))
        text = out.call_args.args[0]
        self.assertNotIn('actually signed back in', text)
        self.assertNotIn('Original hands request', text)
        self.assertNotIn('Never reboot', text)

    def test_missing_or_quiet_origin_refused(self):
        with self.assertRaises(ValueError):
            self.nod.register_local({'requests': {}}, 'r1', None)
        args = argparse.Namespace(origin_session=self.nod.QUIET_CHIEF, origin_directory='/quiet',
                                  reference='ref', limits='none')
        with self.assertRaises(ValueError):
            self.nod.binding(args)

    def test_multi_answer_reordering_is_not_a_new_event(self):
        a = self.answer.pop('decision')
        b = dict(a, id='a2', option_id='later')
        self.answer.update(decisions=[a, b])
        self.register()
        self.answer.update(decisions=[b, a])
        self.register()
        self.assertEqual(len(self.read()['requests']['r1']['events']), 1)

    def ask_args(self, **kw):
        return argparse.Namespace(**dict(dict(file=None, channel='chief', image=None, recommended=None,
            recommendation=None, dry_run=False, origin_session=None, origin_directory=None,
            reference=None, limits=None, answer_route='origin'), **kw))

    def fresh_ask(self, args=None, payload=None):
        def server(method, path, *a, **kw):
            if method == 'POST':
                return {'request_id':'r1'}
            return self.fetch(method, path)
        card={'title':'Ship the fix?', 'recommended':'yes', 'default':'No change.', 'options':[
            {'id':'yes','label':'Ship','description':'Ship today.'},
            {'id':'no','label':'Wait','description':'Keep this version.'}]}
        card.update(payload or {})
        # Sender authorization is separately tested with real pointer fixtures in
        # test_chief_nod. This suite isolates historical continuation/dedupe behavior.
        with patch.object(self.nod, 'call', side_effect=server) as api, patch('builtins.print'), \
             patch.object(self.nod,'decision_sender',side_effect=lambda _:self.nod.native_origin.return_value):
            with patch.object(self.nod.sys, 'stdin', io.StringIO(json.dumps(card))):
                self.nod.ask(args or self.ask_args())
        return api

    def test_plain_ask_binds_env_native_location_and_generates_stable_identity(self):
        with patch.dict(os.environ, {'OPENCODE_SESSION_ID':'ses_lead'}):
            with patch.object(self.nod, 'native_origin', return_value={'session':'ses_lead','directory':'/actual/worktree'}) as lookup:
                api = self.fresh_ask()
                lookup.assert_called_once_with('ses_lead', None)
                row = self.read()['requests']['r1']
                key = next(iter(self.read()['creates']))
                self.assertTrue(key.startswith('chief-nod:'))
                self.assertEqual(row['origin'], {'session':'ses_lead','directory':'/actual/worktree',
                                                'reference':key,'limits':None})
                self.assertEqual(row['delivery_mode'], 'origin-wake-v1')
                self.assertEqual(row['decision'], self.answer)  # exact raw answer retained
                self.assertEqual(api.call_args_list[0].args[2]['idempotency_key'], key)
                with self.assertRaises(ValueError):
                    self.fresh_ask()  # same generated identity cannot blindly POST again

    def test_direct_wake_chief_or_lead_ignores_runner_env_and_legacy_pointer(self):
        for sid in ('ses_current_chief', 'ses_lead'):
            with self.subTest(sid=sid):
                if (self.home/'state.json').exists():
                    (self.home/'state.json').unlink()  # isolated fixture state only
                with patch.object(self.nod, 'native_origin', return_value={'session':sid,'directory':'/owner'}):
                    self.fresh_ask(self.ask_args(origin_session=sid, origin_directory='/owner',
                                                reference='exact private ref', limits='exact optional limits'))
                sends=[]
                def native(argv, **kwargs):
                    self.assertNotIn('--goal', argv)
                    self.assertEqual(argv[argv.index('--session')+1], sid)
                    if argv[2] == 'status':
                        return argparse.Namespace(returncode=0,stdout=json.dumps({'status':'ok','sessionId':sid,
                                                  'directory':'/owner','sessionStatus':{'type':'idle'}}))
                    sends.append(argv)
                    return argparse.Namespace(returncode=0)
                with patch.dict(os.environ, {'OPENCODE_SESSION_ID':'ses_wrong_runner'}), patch.object(self.nod, 'live_ops', side_effect=AssertionError('new ask must not route via Ops')):
                    with patch.object(self.nod, 'native_origin', return_value={'session':sid,'directory':'/owner'}), patch.object(self.nod.shutil,'which',return_value='/fixture/cli'), patch.object(self.nod.subprocess,'run',side_effect=native):
                        for _ in range(2):
                            with self.nod.state() as (data, save):
                                self.nod.deliver(data, save)
                self.assertEqual(len(sends),1)
                wake=sends[0][sends[0].index('--prompt')+1]
                self.assertLess(len(wake),1200)
                self.assertIn('DATA',wake)
                self.assertIn('manual stops/holds',wake)
                self.assertIn('exact optional limits',wake)
                self.assertIn('chief-nod show r1',wake)
                self.assertEqual(self.event()[1]['state'],'sent')

    def test_no_env_origin_refuses_before_any_card(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.nod, 'call') as api:
            with patch.object(self.nod.sys, 'stdin',io.StringIO('{"title":"Ask"}')):
                with self.assertRaises(ValueError):
                    self.nod.ask(self.ask_args())
            api.assert_not_called()
        self.assertFalse((self.home/'state.json').exists())

    def test_native_lookup_uses_authoritative_location_and_refuses_mismatch(self):
        body={'status':'ok','sessions':[{'id':'ses_lead','location':{'directory':'/real/worktree'}}]}
        result=argparse.Namespace(returncode=0,stdout=json.dumps(body))
        with patch.object(self.nod.shutil,'which',return_value='/fixture/cli'), patch.object(self.nod.subprocess,'run',return_value=result):
            self.assertEqual(self.nod.native_origin('ses_lead'),{'session':'ses_lead','directory':'/real/worktree'})
            for sid,directory in (('ses_missing',None),('ses_lead','/guessed/chief')):
                with self.assertRaises(ValueError):
                    self.nod.native_origin(sid,directory)

    def test_heartbeat_internal_route_cannot_create_new_card(self):
        with patch.dict(os.environ, {'OPENCODE_SESSION_ID':'ses_wrong_host'}), patch.object(self.nod,'native_origin',side_effect=AssertionError('bus must not inspect env origin')):
            with self.assertRaises(ValueError):
                self.fresh_ask(self.ask_args(answer_route='heartbeat-bus'),{'idempotency_key':'heartbeat:event-1'})
        self.assertFalse((self.home/'state.json').exists())

    def test_unscoped_old_heartbeat_call_refuses_instead_of_direct_duplicate(self):
        with patch.object(self.nod,'native_origin',side_effect=AssertionError('reserved bus identity')):
            with self.assertRaises(ValueError):
                self.fresh_ask(payload={'title':'Old cached bus call','idempotency_key':'heartbeat:event'})
        self.assertFalse((self.home/'state.json').exists())

    def test_existing_card_never_acquires_new_route_on_server_dedupe(self):
        self.register('already handled; actual fixture provenance')
        before=self.read()['requests']['r1']
        with patch.object(self.nod,'native_origin',return_value={'session':'ses_original','directory':'/original'}):
            with self.assertRaises(ValueError):
                self.fresh_ask(self.ask_args(origin_session='ses_original',origin_directory='/original',
                    reference=self.origin['reference'],limits=self.origin['limits']))
        self.assertEqual(self.read()['requests']['r1'],before)

    def test_runner_attests_loaded_code_not_replaced_path(self):
        loaded=self.nod.RUNNER_CODE_SHA256
        Path(self.nod.__file__).write_text('# replaced fixture path after process load')
        args=argparse.Namespace(cmd='run',seconds=1,deliver=False)
        with patch.object(self.nod.time,'monotonic',side_effect=[0,0,2,2]):
            self.nod.continuation(args)
        self.assertEqual(self.read()['runner_code_sha256'],loaded)
        self.assertEqual(self.read()['runner_pid'],os.getpid())


if __name__ == '__main__':
    unittest.main()
