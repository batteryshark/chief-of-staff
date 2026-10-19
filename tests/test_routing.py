import copy
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from runway.policy import decide, timestamp
from runway.ledger import Ledger
from runway.cli import handle, LocalAPI

NOW = 1800000000


def source(name, remaining=60, reset=NOW + 3600):
    return {'id': name, 'slug': name, 'provider': name, 'account': '', 'enabled': True,
            'archived': False, 'kind': 'plan', 'needs_login': False,
            'latest': {'observed_at': timestamp(NOW-10), 'fresh_until': timestamp(NOW+3600),
                       'reason': None, 'windows': [
                {'id': '5h', 'unit': 'percent', 'remaining_percent': remaining,
                 'resets_at': timestamp(reset), 'stale': False},
                {'id': 'weekly', 'unit': 'percent', 'remaining_percent': remaining,
                 'resets_at': timestamp(NOW+86400), 'stale': False}]}}


def route(name):
    return {'id': name, 'host': 'local', 'model': name+'/strong', 'provider': name,
            'account': '', 'source': name, 'pool': name, 'windows': 'all',
            'categories': ['trivial', 'research', 'implement', 'hard'], 'max_parallel': 2}


def model(name):
    return {'providerID': name, 'id': 'strong', 'enabled': True, 'status': 'active',
            'capabilities': {'tools': True, 'input': ['text']}, 'variants': [{'id':'high'}],
            'limit': {'context': 128000}}


def fixture():
    return ({'version': 1, 'routes': [route('gpt'), route('claude')]},
            {'schema_version': 2, 'passive': True, 'sources': [source('gpt'), source('claude',80)]},
            {'directory': '/repo', 'observed_at': timestamp(NOW), 'models': [model('gpt'), model('claude')]},
            {'job': 'job', 'scope': '/project', 'directory': '/repo', 'category': 'hard', 'size': 'medium', 'writer': True})


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.config, self.snapshot, self.catalog, self.task = fixture()

    def run_policy(self, attempts=(), pref=None, now=NOW):
        return decide(self.config, self.snapshot, self.catalog, self.task, attempts, pref, now)

    def preference(self):
        return {'scope':'/project', 'source_id':'gpt', 'window_id':'5h',
                'reset_at':timestamp(NOW+3600), 'expires_at':timestamp(NOW+3600)}

    def test_normal_preserves_tighter_runway(self):
        self.assertEqual(self.run_policy()['selected']['route'], 'claude')

    def test_preference_uses_expiring_allowance(self):
        self.assertEqual(self.run_policy(pref=self.preference())['selected']['route'], 'gpt')

    def test_preference_never_overrides_weekly_exhaustion(self):
        self.snapshot['sources'][0]['latest']['windows'][1]['remaining_percent'] = 0
        self.assertEqual(self.run_policy(pref=self.preference())['selected']['route'], 'claude')

    def test_only_selected_window_reserve_is_waived(self):
        self.snapshot['sources'][0]['latest']['windows'][0]['remaining_percent'] = 4
        self.assertEqual(self.run_policy(pref=self.preference())['selected']['route'], 'gpt')
        self.snapshot['sources'][0]['latest']['windows'][1]['remaining_percent'] = 4
        self.assertEqual(self.run_policy(pref=self.preference())['selected']['route'], 'claude')

    def test_preference_expires_and_does_not_follow_next_epoch_or_other_scope(self):
        for key, value in [('expires_at', timestamp(NOW)), ('reset_at', timestamp(NOW+4000)), ('scope','elsewhere')]:
            p = self.preference(); p[key] = value
            self.assertEqual(self.run_policy(pref=p)['selected']['route'], 'claude')

    def test_unknown_capacity_is_not_unlimited(self):
        for mutation in ('missing','stale','expired','nonfinite','wrongunit','account','future','fallback'):
            with self.subTest(mutation):
                _, self.snapshot, _, _ = fixture()
                s = self.snapshot['sources'][1]; latest=s['latest']; w=latest['windows'][0]
                if mutation=='missing': latest['windows']=[]
                if mutation=='stale': latest['fresh_until']=timestamp(NOW-1)
                if mutation=='expired': w['resets_at']=timestamp(NOW)
                if mutation=='nonfinite': w['remaining_percent']=float('nan')
                if mutation=='wrongunit': w['unit']='USD'
                if mutation=='account': s['account']='different'
                if mutation=='future': latest['observed_at']=timestamp(NOW+600)
                if mutation=='fallback': latest['reason']='historical recording'
                self.assertEqual(self.run_policy()['selected']['route'],'gpt')

    def test_missing_catalog_disabled_unsupported_variant_and_quality_floor(self):
        for mutation in ('empty','disabled','variant','category','context','tools'):
            with self.subTest(mutation):
                self.config, _, self.catalog, _ = fixture()
                if mutation=='empty': self.catalog['models']=[]
                if mutation=='disabled': self.catalog['models'][1]['enabled']=False
                if mutation=='variant': self.config['routes'][1]['variant']='unavailable'
                if mutation=='category': self.config['routes'][1]['categories']=['trivial']
                if mutation=='context': self.catalog['models'][1]['limit']['context']=1; self.task['context']=100
                if mutation=='tools': self.catalog['models'][1]['capabilities']['tools']=False
                selected=self.run_policy()['selected']
                self.assertEqual(selected['route'] if selected else None,None if mutation=='empty' else 'gpt')

    def test_other_group_exhaustion_does_not_block_mapped_group(self):
        s = self.snapshot['sources'][1]
        s['latest']['windows'].append({'id':'other','unit':'percent','remaining_percent':0,'stale':False})
        self.config['routes'][1]['windows']=['5h','weekly']
        self.assertEqual(self.run_policy()['selected']['route'],'claude')
        s['latest']['windows'].pop(0)
        self.assertEqual(self.run_policy()['selected']['route'],'gpt')

    def test_all_windows_includes_new_provider_buckets(self):
        self.snapshot['sources'][1]['latest']['windows'].append({'id':'new','unit':'percent','remaining_percent':0})
        self.assertEqual(self.run_policy()['selected']['route'],'gpt')

    def test_completed_charge_persists_until_measurement_catches_up(self):
        a={'pool':'claude','state':'completed','finished_at':timestamp(NOW),
           'reservation':[{'window_id':'weekly','reset_at':timestamp(NOW+86400),'percent':75}]}
        self.assertEqual(self.run_policy([a])['selected']['route'],'gpt')
        self.snapshot['sources'][1]['latest']['observed_at']=timestamp(NOW)
        self.assertEqual(self.run_policy([a])['selected']['route'],'claude')

    def test_source_aliases_cannot_evade_pool_caps(self):
        r=copy.deepcopy(self.config['routes'][0]);r.update(id='alias',pool='alternate',source='source-id-alias')
        self.config['routes'].append(r)
        with self.assertRaisesRegex(ValueError,'share pool'): self.run_policy()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.db'
        self.ledger=Ledger(self.path); self.addCleanup(self.ledger.close)
        self.config,self.snapshot,self.catalog,self.task=fixture()

    def prepare(self, ledger=None, task=None, now=NOW):
        return (ledger or self.ledger).plan(self.config,self.snapshot,self.catalog,task or self.task,now,admit=True)

    def bind(self,a):
        provider, mid=a['model'].split('/',1)
        return self.ledger.bind(a['id'],{'id':'ses_worker','location':{'directory':'/repo'},
                                'model':{'providerID':provider,'id':mid}},NOW+1)

    def evidence(self):
        return {'session_id':'ses_worker','idle':True,'inbox_empty':True,'outcome':'succeeded',
                'tools_reconciled':True,'effects_reconciled':True,'last_idle_at':timestamp(NOW+2)}

    def checkpoint(self):
        return dict(objective='fix',directory='/repo',changes='file.py',tests='pass',next='review',side_effects='none')

    def test_idempotence_and_restart_keep_admission(self):
        first=self.prepare(); self.assertTrue(first['dispatch_allowed'])
        self.assertEqual(first['args']['title'],'job')
        other=Ledger(self.path)
        try:
            again=self.prepare(other)
            self.assertFalse(again['dispatch_allowed'])
            self.assertEqual(again['attempt']['id'],first['attempt']['id'])
        finally:other.close()

    def test_shared_pool_parallel_admissions_are_atomic(self):
        self.config['routes']=self.config['routes'][:1]
        barrier=threading.Barrier(4); results=[]
        def run(i):
            ledger=Ledger(self.path)
            task={**self.task,'job':str(i),'writer':False}
            try:
                barrier.wait(); results.append(self.prepare(ledger,task)['dispatch_allowed'])
            finally: ledger.close()
        threads=[threading.Thread(target=run,args=(i,)) for i in range(4)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count(True),2)

    def test_one_writer_per_directory_even_across_provider_pools(self):
        self.prepare()
        self.assertFalse(self.prepare(task={**self.task,'job':'different'})['dispatch_allowed'])

    def test_no_release_for_busy_queued_or_unreconciled_worker(self):
        a=self.prepare()['attempt']; self.bind(a)
        for field in ('idle','inbox_empty','tools_reconciled','effects_reconciled'):
            evidence=self.evidence();evidence[field]=False
            with self.assertRaises(ValueError):
                self.ledger.finish(a['id'],'quiescent',self.checkpoint(),evidence,NOW+3)
        self.assertEqual(self.ledger.get(a['id'])['state'],'running')

    def test_recovery_continues_same_session_and_keeps_checkpoint(self):
        a=self.prepare()['attempt'];self.bind(a)
        self.ledger.finish(a['id'],'quiescent',self.checkpoint(),self.evidence(),NOW+3)
        self.snapshot['sources'][1]['latest']['windows'][0]['remaining_percent']=0
        next=self.prepare(now=NOW+4)
        self.assertTrue(next['dispatch_allowed']);self.assertEqual(next['action'],'session.send')
        self.assertEqual(next['args']['sessionId'],'ses_worker');self.assertEqual(next['args']['model'],'gpt/strong')
        self.assertEqual(next['attempt']['checkpoint']['next'],'review')
        self.assertNotEqual(next['args']['messageId'],a['message_id'])

    def test_ambiguous_delivery_never_expires_and_cannot_be_marked_unsent_after_bind(self):
        a=self.prepare()['attempt'];self.bind(a)
        self.ledger.finish(a['id'],'uncertain',{}, {}, NOW+3)
        with self.assertRaises(ValueError):
            self.ledger.finish(a['id'],'unsent',{}, {'confirmed_not_sent':True}, NOW+4)
        self.assertFalse(self.prepare(now=NOW+864000)['dispatch_allowed'])

    def test_cancelled_and_completed_jobs_do_not_auto_resume(self):
        for state in ('cancelled','completed'):
            task={**self.task,'job':state}
            a=self.prepare(task=task)['attempt'];self.bind(a)
            self.ledger.finish(a['id'],state,{},self.evidence(),NOW+3)
            with self.assertRaises(ValueError):self.prepare(task=task,now=NOW+4)

    def test_prior_turn_success_cannot_complete_a_new_attempt(self):
        a=self.prepare()['attempt'];self.bind(a)
        evidence=self.evidence();evidence['last_idle_at']=timestamp(NOW-1)
        with self.assertRaisesRegex(ValueError,'terminal execution'):
            self.ledger.finish(a['id'],'completed',{},evidence,NOW+3)

    def test_preference_survives_restart_but_expires(self):
        self.ledger.prefer(self.config,self.snapshot,'/project','gpt','5h',NOW)
        other=Ledger(self.path)
        try:
            self.assertEqual(other.preference('/project')['expires_at'],timestamp(NOW+3600))
            self.assertEqual(self.prepare(other)['selected']['route'],'gpt')
        finally:other.close()

    def test_wrong_model_binding_and_changed_directory_fail(self):
        a=self.prepare()['attempt']
        with self.assertRaises(ValueError):self.ledger.bind(a['id'],{'id':'ses_x','location':{'directory':'/other'}},NOW)
        with self.assertRaises(ValueError):self.prepare(task={**self.task,'directory':'/other'})

class TransportTests(unittest.TestCase):
    def test_local_auth_never_sent_to_remote_or_userinfo_url(self):
        for url in ('https://example.com','http://evil/','http://user@localhost:1','http://localhost/path'):
            with self.assertRaises(ValueError):LocalAPI(url,auth=True)

    def test_catalog_uses_location_deep_object_and_retries_empty_snapshot(self):
        api=LocalAPI('http://127.0.0.1:1234')
        directory=str(Path('/tmp').resolve())
        response={'location':{'directory':directory},'data':[model('gpt')]}
        with patch.object(api,'get',side_effect=[{'location':{'directory':directory},'data':[]},response]) as get, patch('runway.cli.time.sleep'):
            result=api.catalog(directory,['gpt/strong'])
        self.assertEqual(result['models'][0]['id'],'strong')
        self.assertEqual(get.call_args.kwargs, {'location[directory]':directory})
