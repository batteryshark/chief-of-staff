"""Offline exact-file refresh and decided Docket contract, never a real CLI/API call."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tower_refresh as refresh
import tower_refresh_docket as docket
import tower_export as export

T='2026-01-01T00:00:00Z'


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); (self.root/'snap').mkdir()
        self.where=lambda path:{'root':str(self.root),'path':path}
        self.header='Status: Building\nUsable now: The phone page works.\nLeft: Finish review.\nWaiting on: Nothing from you.\nNeeds you: false\n## Details\nTechnical history'
        (self.root/'lead.md').write_text(self.header)
        p={'id':'demo','outcome_id':'outcome','title':'Demo','status':'Old','root':str(self.root/'snap'),
           'files':[{'id':'lead','path':'lead.md','label':'Lead'}],'export':self.where('projection.json')}
        self.row={'project':p,'knowledge':[]}
        self.out={'version':1,'project_id':'demo','outcome_id':'outcome','generated_at':T,
                  'knowledge':{'state':'available','provenance':'API','observed_at':T,'items':[]},'activity':[]}
        self.write('export.json',{'version':1,'projects':[self.row]}); self.write('projection.json',self.out)
        self.write('manifest.json',{'version':1,'projects':[p,dict(p,id='other',status='Held')]})
        self.spec={'project_id':'demo','session':'ses_demo','directory':str(self.root),'header':self.where('lead.md'),
                   'copies':[{'source':self.where('lead.md'),'target':{'root':str(self.root/'snap'),'path':'lead.md'}}]}
        self.config={'version':1,'export_config':self.where('export.json'),'manifest':self.where('manifest.json'),'projects':[self.spec]}
        self.periodic={'version':1,'kind':'periodic'}
        self.m={'id':'mil_'+'a'*64,'version':1,'lead_session':'ses_demo','directory':str(self.root),
                'milestone_at':T,'observed_at':T,'milestone_ref':'Actual accepted marker','roster_state':'hold',
                'provenance':'recorded_marker_observation'}

    def write(self,path,value): (self.root/path).write_text(json.dumps(value))
    def result(self): return json.loads((self.root/'projection.json').read_text())
    def run_refresh(self,notice=None,**kwargs): return refresh.refresh(self.config,notice or self.periodic,**kwargs)

    def test_periodic_preserves_true_cache_and_no_fake_activity(self):
        self.run_refresh(); out=self.result()
        self.assertEqual(out['knowledge'],self.out['knowledge']); self.assertEqual(out['activity'],[])
        self.assertEqual(out['summary']['usable now'],'The phone page works.')
        observed=out['summary']['observed_at']; self.run_refresh()
        self.assertEqual(self.result()['summary']['observed_at'],observed)
        manifest=json.loads((self.root/'manifest.json').read_text())
        self.assertEqual([p['status'] for p in manifest['projects']],['Building','Held'])
        self.assertEqual((self.root/'snap/lead.md').read_text(),self.header)

    def test_changed_jargon_retains_old_source_time_and_reports_recovery(self):
        self.run_refresh(); old=self.result()['summary']['observed_at']
        (self.root/'lead.md').write_text(self.header.replace('The phone page works.','MAINabc1234 /private/source'))
        result=self.run_refresh(); out=self.result()
        self.assertEqual(result['stale_sources'],['demo']); self.assertEqual(out['summary']['observed_at'],old)
        self.assertEqual(out['summary']['usable now'],'The phone page works.')
        self.assertIn(refresh.STALE,out['summary']['provenance'])

    def test_status_cannot_break_existing_manifest_bound(self):
        self.assertIsNone(refresh.principal_header(self.header.replace('Status: Building','Status: '+'x'*81).encode()))

    def test_digest_migration_only_unchanged_source(self):
        (self.root/'lead.md').write_text('# Old technical history')
        self.spec['migration']={'sha256':refresh.digest((self.root/'lead.md').read_bytes()),'status':'Ready',
            'summary':{'observed_at':T,'provenance':'Reviewed migration','reference':'source digest',
                       'usable now':'The phone page works.','left':'Review.','waiting on':'Nothing from you.','needs_you':False}}
        self.run_refresh(); self.assertEqual(self.result()['summary']['observed_at'],T)
        (self.root/'lead.md').write_text('# Changed technical history')
        self.assertEqual(self.run_refresh()['stale_sources'],['demo'])

    def test_marker_idempotent_returned_id_and_origin_only(self):
        notice={'version':1,'kind':'milestone','marker':self.m}
        self.run_refresh(notice); self.run_refresh(notice,markers=[self.m])
        activity=self.result()['activity']; self.assertEqual(len(activity),1)
        self.assertEqual(activity[0]['id'],self.m['id']); self.assertEqual(activity[0]['at'],T)
        self.assertEqual(activity[0]['label'],'New work was delivered.')
        self.assertNotEqual(activity[0]['label'],self.result()['summary']['usable now'])
        wrong=dict(self.m,id='mil_'+'b'*64,lead_session='ses_other')
        self.run_refresh(markers=[wrong]); self.assertEqual(len(self.result()['activity']),1)

    def test_privacy_failure_preserves_previous_documents_and_projection(self):
        self.run_refresh(); old=(self.root/'projection.json').read_bytes(); doc=(self.root/'snap/lead.md').read_bytes()
        (self.root/'lead.md').write_text(self.header+'\napi_key=do-not-copy')
        with self.assertRaises(ValueError): self.run_refresh()
        self.assertEqual((self.root/'projection.json').read_bytes(),old)
        self.assertEqual((self.root/'snap/lead.md').read_bytes(),doc)

    def test_exact_text_redaction_default_refusal_original_digest_and_counts(self):
        raw=b'# Legacy history\nBearer fixture-value\naccess_token=example\n'
        (self.root/'lead.md').write_bytes(raw)
        self.spec['migration']={'sha256':refresh.digest(raw),'status':'Ready',
            'summary':{'observed_at':T,'provenance':'Reviewed migration','reference':'original digest',
                       'usable now':'The page works.','left':'Review.','waiting on':'Nothing from you.'}}
        old=(self.root/'projection.json').read_bytes()
        with self.assertRaises(ValueError): self.run_refresh()
        self.spec['copies'][0]['redact_private_patterns']=True
        with self.assertRaises(ValueError): self.run_refresh() # Header opt-in is independent/exact.
        self.assertEqual((self.root/'projection.json').read_bytes(),old)
        self.assertFalse((self.root/'snap/lead.md').exists())
        self.spec['header']['redact_private_patterns']=True
        result=self.run_refresh()
        self.assertEqual(result['redactions'],4)
        copied=(self.root/'snap/lead.md').read_text()
        self.assertEqual(copied.count('[redacted private-pattern text]'),2)
        self.assertNotIn('fixture-value',copied); self.assertNotIn('example',copied)
        self.assertEqual((self.root/'lead.md').read_bytes(),raw)
        self.assertEqual(self.result()['summary']['observed_at'],T) # Original-byte migration matched.
        (self.root/'lead.md').write_bytes(raw+b'Bearer new-fixture-pattern\n')
        result=self.run_refresh()
        self.assertEqual(result['stale_sources'],['demo']) # Redacted bytes never bind migration.
        self.assertEqual(self.result()['summary']['observed_at'],T)
        self.assertNotIn('new-fixture-pattern',(self.root/'snap/lead.md').read_text())

    def test_redaction_flags_strict_and_no_partial_write_after_later_failure(self):
        self.run_refresh(); before=(self.root/'projection.json').read_bytes(); doc=(self.root/'snap/lead.md').read_bytes()
        self.spec['copies'][0]['redact_private_patterns']=True
        self.spec['header']['redact_private_patterns']=True
        (self.root/'lead.md').write_text(self.header+'\nBearer reviewed-fixture\n')
        self.row['project']['files'].append({'id':'extra','path':'extra.md','label':'Extra'})
        self.write('export.json',{'version':1,'projects':[self.row]})
        (self.root/'extra.md').write_text('Bearer unapproved-fixture')
        self.spec['copies'].append({'source':self.where('extra.md'),'target':{'root':str(self.root/'snap'),'path':'extra.md'}})
        with self.assertRaises(ValueError): self.run_refresh()
        self.assertEqual((self.root/'projection.json').read_bytes(),before)
        self.assertEqual((self.root/'snap/lead.md').read_bytes(),doc)
        for value in ('true',1,None,[]):
            self.spec['header']['redact_private_patterns']=value
            with self.assertRaises(ValueError): refresh.configuration(self.config)
            self.spec['header']['redact_private_patterns']=True
            self.spec['copies'][0]['redact_private_patterns']=value
            with self.assertRaises(ValueError): refresh.configuration(self.config)
            self.spec['copies'][0]['redact_private_patterns']=True

    def test_normal_roles_discover_cache_command_without_growth(self):
        import lean_roles
        root=Path(__file__).resolve().parents[1]
        for role,lines,bytes_ in (('lead',36,3076),('chief',49,4310)):
            body=(root/f'kits/reset/{role}.md').read_text()
            self.assertIn('registered Tower notes',body); self.assertIn('real work',body)
            self.assertIn('reset-checkpoint',body)
            self.assertLessEqual(len(body.splitlines()),lines); self.assertLessEqual(len(body.encode()),bytes_)
            lean_roles.budget(role,body,'/brief')
        checkpoint=(root/'kits/reset/skills/checkpoint/SKILL.md').read_text()
        self.assertIn('~/.local/share/chief-of-staff/tower/tower_refresh.py --knowledge ~/.chief-of-staff/tower/refresh-config.json',checkpoint)
        self.assertIn('If either is absent or inaccessible, skip',checkpoint)
        self.assertNotIn('<kit>',checkpoint); self.assertNotIn('<registered-config>',checkpoint)

    def test_path_extra_event_and_nonboolean_fail_closed(self):
        for mutate in (lambda:self.config.update(command='bad'), lambda:self.spec['header'].update(path='../lead.md'),
                       lambda:self.spec['copies'][0]['target'].update(path='other.md')):
            original=copy.deepcopy(self.config); mutate()
            with self.assertRaises((ValueError,OSError)): self.run_refresh()
            self.config=original; self.spec=self.config['projects'][0]
        with self.assertRaises(ValueError): refresh.invalidation(dict(self.periodic,argv=['evil']))
        bad=copy.deepcopy(self.out); bad['knowledge']['observed_at']='2099-01-01T00:00:00Z'
        with self.assertRaises(ValueError): export.schema.projection(bad,'demo','outcome')

    def test_genuine_context_entry_uses_exact_directory_and_preserves_summary(self):
        self.run_refresh(); summary=self.result()['summary']; calls=[]
        def reader(directory): calls.append(directory); return {'notes':[],'todos':[],'plans':[]}
        refresh.refresh_knowledge(self.config,reader)
        self.assertEqual(calls,[str(self.root)]); self.assertEqual(self.result()['summary'],summary)
        self.assertNotEqual(self.result()['knowledge']['observed_at'],T)
        old=(self.root/'projection.json').read_bytes()
        with self.assertRaises(ValueError): refresh.refresh_knowledge(self.config,lambda _: (_ for _ in ()).throw(ValueError()))
        self.assertEqual((self.root/'projection.json').read_bytes(),old)


class DocketContractTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc); self.calls=[]
        self.s={'item_id':'dkt_tower_refresh','status':'pending','purpose':'project_pages','every_seconds':900,
                'anchor':T,'next_fire_at':None,'until':(self.now+timedelta(days=30)).isoformat(),
                'lease_expired':False,'cancelled_at':None,'last_occurrence':None}
    def envelope(self,s): return {'version':1,'source':'docket.tower-refresh-schedule','observed_at':T,'changed':False,'schedule':s}
    def client(self):
        def request(exe,argv):
            self.calls.append((exe,argv))
            if argv[:2]==['tower-refresh','ensure']: self.s['until']=argv[3]
            return self.envelope(self.s)
        return docket.Docket('/fixed/docket',request)
    def test_active_cancelled_and_expired_no_resurrection(self):
        self.assertEqual(self.client().reconcile(self.now),'active')
        self.s.update(status='cancelled',cancelled_at=T)
        self.assertEqual(self.client().reconcile(self.now),'cancelled')
        self.s.update(status='pending',cancelled_at=None,lease_expired=True)
        with self.assertRaises(ValueError): self.client().reconcile(self.now)
        self.assertTrue(all(argv==['tower-refresh','show','--json'] for _,argv in self.calls))
    def test_renew_under_seven_days_fixed_until_and_anchor(self):
        self.s['until']=(self.now+timedelta(days=2)).isoformat()
        self.assertEqual(self.client().reconcile(self.now),'renewed')
        self.assertEqual(self.calls[-1][1][:3],['tower-refresh','ensure','--until'])
        self.assertLessEqual(docket.future_time(self.calls[-1][1][3])-self.now,timedelta(days=90))
    def test_unknown_not_empty_and_marker_projection(self):
        client=docket.Docket('/fixed',lambda *_:{'version':1,'error':{'code':'unavailable','detail':'retry'}})
        with self.assertRaises(ValueError): client.markers()
        with self.assertRaises(ValueError): client.reconcile(self.now)
        client=docket.Docket('/fixed',lambda *_:{'version':1,'source':'docket.project-markers','observed_at':T,'complete':True,'markers':[]})
        self.assertEqual(client.markers(),[])


if __name__=='__main__': unittest.main()
