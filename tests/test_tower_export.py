"""Offline synthetic records only; no cards, inherited endpoint calls or private reads."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import tower_export as export
import tower_schema as schema
import lean_roles
import render

T0='2026-01-01T10:00:00Z'
T1='2026-01-01T11:00:00Z'


class TowerExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.project={'id':'project','outcome_id':'outcome','root':str(self.root),'title':'Example','status':'active',
                      'files':[],'images':[],'export':{'root':str(self.root),'path':'project.json'}}
        self.row={'project':self.project,'knowledge':[{'id':'native-todo','kind':'todo','title':'Next'}]}
        self.native={'notes':[],'todos':[{'id':'native-todo','text':'Safe work','completed':False}],'plans':[]}

    def build(self):
        return export.build(self.row,reader=lambda _:self.native)

    def test_supported_transport_exact_inherited_caller_only(self):
        env={'OPENCHAMBER_AGENT_TOOL_URL':'http://127.0.0.1:9000/agent','OPENCHAMBER_AGENT_TOOL_TOKEN':'fixture', 'OPENCODE_SESSION_ID':'ses_actual'}
        response=Mock(); response.__enter__=Mock(return_value=response); response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({'schemaVersion':1,'ok':True,'action':'knowledge.list','data':self.native}).encode()
        client=Mock(); client.open.return_value=response
        self.assertEqual(export.knowledge_read(str(self.root),env,client),self.native)
        request=client.open.call_args.args[0]
        self.assertEqual(json.loads(request.data),{'tool':'openchamber_knowledge','sessionID':'ses_actual','input':{'action':'knowledge.list','directory':str(self.root)}})
        self.assertEqual(client.open.call_args.kwargs,{'timeout':5}); response.read.assert_called_once_with(export.LIMIT+1)
        for url in ('http://remote/agent','file:///private','http://fixture@localhost/agent','http://127.0.0.1/agent#fragment'):
            with self.assertRaises(ValueError): export.knowledge_read(str(self.root),dict(env,OPENCHAMBER_AGENT_TOOL_URL=url),client)
        with self.assertRaises(ValueError): export.knowledge_read(str(self.root),{},client)
        with self.assertRaises(ValueError): export.NoRedirect().redirect_request(None)
        for bad in ({'schemaVersion':True,'ok':True,'action':'knowledge.list','data':{}}, {'schemaVersion':1,'ok':True,'action':'knowledge.save','data':{}}):
            response.read.return_value=json.dumps(bad).encode()
            with self.assertRaises(ValueError): export.knowledge_read(str(self.root),env,client)
        response.read.return_value=b'x'*(export.LIMIT+1)
        with self.assertRaises(ValueError): export.knowledge_read(str(self.root),env,client)

    def test_native_ids_states_and_explicit_item_allowlist(self):
        self.native['todos'].append({'id':'private','text':'not selected','completed':True})
        out=self.build(); self.assertEqual(out['knowledge']['items'],[{'id':'native-todo','kind':'todo','title':'Next','body':'Safe work','completed':False}])
        for invalid in (0,1,'false',None):
            self.native['todos'][0]['completed']=invalid
            self.assertEqual(self.build()['knowledge']['state'],'unavailable')
        self.assertEqual(export.project_knowledge(self.row,lambda _: (_ for _ in ()).throw(ValueError()))['state'],'unavailable')

    def test_genuine_todo_text_shape_and_notes_body_no_inferred_fallback(self):
        self.row['knowledge'].append({'id':'synthetic-note','kind':'note','title':'Decision'})
        self.native['notes']=[{'id':'synthetic-note','body':'Actual note field','text':'not the note field'}]
        out=self.build()['knowledge']
        self.assertEqual(out['state'],'available')
        self.assertEqual([i['body'] for i in out['items']],['Safe work','Actual note field'])
        for invalid in (None,False,3,[],{}):
            self.native['todos'][0]['text']=invalid
            self.native['todos'][0]['body']='Wrong legacy field must not rescue it'
            self.assertEqual(self.build()['knowledge']['state'],'unavailable')
        self.native['todos'][0].pop('text')
        self.assertEqual(self.build()['knowledge']['state'],'unavailable')

    def test_generated_at_is_sampled_after_network_and_answer_reads(self):
        from datetime import datetime, timezone
        self.row['acceptance_request_id']='synthetic-request'
        reads=[]
        def reader(_): reads.append('knowledge'); return self.native
        def acceptance(_):
            reads.append('answer')
            return {'project_id':'project','outcome_id':'outcome','state':'accepted','request_state':'answered',
                'request_id':'synthetic-request','requested_at':T0,'reference':'outcome','provenance':'chief-only Nod answer projection',
                'answer':{'type':'nod.answer','id':'synthetic-answer','request_id':'synthetic-request','project_id':'project','outcome_id':'outcome',
                          'value':'Accept','answered_at':T1,'reference':'synthetic answer reference','provenance':'actual Nod response'}}
        def now(_):
            self.assertEqual(reads,['knowledge','answer'])
            return datetime(2026,1,1,12,tzinfo=timezone.utc)
        with patch.object(export,'datetime') as clock:
            clock.now.side_effect=now
            out=export.build(self.row,reader,acceptance)
        self.assertEqual(out['generated_at'],'2026-01-01T12:00:00+00:00')
        schema.projection(out,'project','outcome')

    def test_exact_native_plan_path_and_no_symlink_read(self):
        (self.root/'plan.md').write_text('# Plan\n- [ ] Next')
        self.project['files']=[{'id':'plan','path':'plan.md','label':'Plan'}]
        self.row['knowledge']=[{'id':'native-plan','kind':'plan','title':'Plan','file_id':'plan'}]
        self.native['plans']=[{'id':'native-plan','path':str(self.root/'plan.md')}]
        export.configuration({'version':1,'projects':[self.row]})
        self.assertEqual(self.build()['knowledge']['items'][0]['id'],'native-plan')
        self.native['plans'][0]['path']='/unapproved/plan.md'
        self.assertEqual(self.build()['knowledge']['state'],'unavailable')
        (self.root/'link.md').symlink_to(self.root/'plan.md')
        with self.assertRaises(OSError): export.read_exact(str(self.root),'link.md')

    def test_strict_nested_schema_summary_activity_and_identity(self):
        out=self.build(); out['summary']={'observed_at':T0,'reference':'native-note','provenance':'owner status','usable now':'Works'}
        out['activity']=[{'id':'commit-1','project_id':'project','outcome_id':'outcome','kind':'landing','at':T0,'label':'Source landed','reference':'commit abc123','provenance':'Git commit'}]
        schema.projection(out,'project','outcome')
        for section,value in [('knowledge',None),('knowledge',{'state':'available','provenance':'API','items':[[]]}),('summary',[]),('activity',{}),('acceptance',None)]:
            bad=copy.deepcopy(out); bad[section]=value
            with self.assertRaises((ValueError,TypeError)): schema.projection(bad,'project','outcome')
        for field,value in [('version',True),('project_id','other'),('generated_at','2099-01-01T00:00:00Z')]:
            bad=copy.deepcopy(out); bad[field]=value
            with self.assertRaises(ValueError): schema.projection(bad,'project','outcome')
        bad=copy.deepcopy(out); bad['activity'][0]['extra']='no'
        with self.assertRaises(ValueError): schema.projection(bad,'project','outcome')

    def test_optional_reviewed_tower_validator_compatibility(self):
        file=os.environ.get('TOWER_SCHEMA_FILE')
        if not file: self.skipTest('reviewed Tower validator path not supplied')
        spec=importlib.util.spec_from_file_location('reviewed_tower_schema',file)
        validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        out=self.build(); out['summary']={'observed_at':T0,'reference':'native-note','provenance':'owner status','usable now':'Works'}
        validator.project(self.project); validator.projection(out,self.project)
        bad=copy.deepcopy(out); bad['knowledge']['items']*=2
        with self.assertRaises(ValueError): schema.projection(bad,'project','outcome')

    def test_secret_path_rejection_and_atomic_old_bytes_on_failure(self):
        for name in ('../escape.json','.hidden.json','secrets.json','api-key.json','a%2fb.json','a\\b.json'):
            with self.assertRaises(ValueError): export.relative(name,{'.json'})
        for secret in ('Bearer hidden-value','api_key=hidden-value','-----BEGIN RSA PRIVATE KEY-----'):
            with self.assertRaises(ValueError): export.sanitize({'body':secret})
        target=self.project['export']; old=b'old'; (self.root/'project.json').write_bytes(old)
        with patch.object(export.os,'replace',side_effect=OSError('failure')):
            with self.assertRaises(OSError): export.atomic_write(target,self.build())
        self.assertEqual((self.root/'project.json').read_bytes(),old)
        self.assertFalse(list(self.root.glob('.tower-*')))
        out=self.build(); export.atomic_write(target,out)
        self.assertEqual(json.loads((self.root/'project.json').read_text()),out)
        self.assertEqual((self.root/'project.json').stat().st_mode & 0o777,0o600)
        (self.root/'alias.json').symlink_to(self.root/'project.json')
        with self.assertRaises(ValueError): export.atomic_write({'root':str(self.root),'path':'alias.json'},out)

    def test_config_strict_allowlists(self):
        export.configuration({'version':1,'projects':[self.row]})
        for mutate in (lambda r:r.update(extra=True),lambda r:r['project'].update(files=[{'id':'x','path':'../no.md','label':'No'}]),lambda r:r['knowledge'][0].update(extra='x')):
            row=copy.deepcopy(self.row); mutate(row)
            with self.assertRaises(ValueError): export.configuration({'version':1,'projects':[row]})
        row=copy.deepcopy(self.row); row['project']['id']='second'
        with self.assertRaises(ValueError): export.configuration({'version':1,'projects':[self.row,row]})
        for broad in (str(Path.home()),str(Path.home().parent),str(Path.home()/'Projects')):
            with self.assertRaises(ValueError): export.root(broad)

    def test_prompt_line_and_byte_non_growth(self):
        source=(ROOT/'kits/reset/lead.md').read_text()
        self.assertLessEqual(len(source.splitlines()),36); self.assertLessEqual(len(source.encode()),3076)
        lean_roles.body('lead','/fixture')
        for phrase in ('Usable now','Left','Waiting on','Acceptance','Handed to','acceptance answer','independently','skill candidate','Docket routines','holds','Never bypass'):
            self.assertIn(phrase,source)
        self.assertIn('Record lasting preferences',source)
        self.assertIn('New rules replace old',source)
        self.assertIn('reviewed host binding',source)


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); file=root/'nod.py'; file.write_text(render.render('scripts/chief-nod',str(root)))
        spec=importlib.util.spec_from_file_location('tower_nod',file); self.nod=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.nod)
        self.a={'project_id':'project','outcome_id':'outcome','request_id':'request','reference':'outcome report', 'issuer':{'session':'ses_chief','directory':'/chief'},'issuance':'chief-only-v1'}
        self.row={'acceptance':self.a,'origin':self.a['issuer'],'snapshot':{'id':'request','created_at':T0},'decision':{'status':'pending','decisions':[]}}

    def projection(self):
        a=self.nod.acceptance_projection('request',self.row)
        out={'version':1,'project_id':'project','outcome_id':'outcome','generated_at':T1,'acceptance':a}
        schema.projection(out,'project','outcome')
        file=os.environ.get('TOWER_SCHEMA_FILE')
        if file:
            spec=importlib.util.spec_from_file_location('reviewed_acceptance_schema',file)
            validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
            validator.projection(out,{'id':'project','outcome_id':'outcome'})
        return a

    def test_actual_answer_lifecycle_not_delivery_and_exact_schema(self):
        self.assertEqual(self.projection()['request_state'],'pending')
        for status in ('expired','cancelled'):
            self.row['decision']['status']=status; self.assertEqual(self.projection()['request_state'],status)
        self.row['decision']['decision']={'id':'answer','option_id':'accept','created_at':T1}
        self.row['events']={'event':{'state':'uncertain'}}
        a=self.projection(); self.assertEqual(a['state'],'accepted'); self.assertEqual(a['answer']['type'],'nod.answer')
        self.row['decision']['decision']['option_id']='not-yet'; self.assertEqual(self.projection()['state'],'not-yet')
        self.row['decision']['decisions']=[{'id':'conflict'}]
        with self.assertRaises(ValueError): self.projection()

    def test_generic_defaults_require_local_guard_and_image_inputs_before_effects(self):
        self.assertEqual(self.nod.DEFAULT_URL,'http://127.0.0.1:8767')
        self.assertEqual(self.nod.DEFAULT_IMAGE_BASE,'https://chief-images.example.invalid:9443/chief-images')
        with patch.dict(os.environ,{'CHIEF_NOD_RETIRED_SESSION':'','CHIEF_NOD_IMAGE_BASE':''}), patch.object(self.nod.shutil,'which') as lookup, patch.object(self.nod,'call') as api:
            with self.assertRaises(ValueError): self.nod.native_origin('ses_current')
            with self.assertRaises(ValueError): self.nod.publish_image('/not-read.png',True)
            lookup.assert_not_called(); api.assert_not_called()

    def test_saved_acceptance_status_is_read_only_without_reconcile_or_recovery(self):
        from argparse import Namespace
        home=Path(self.tmp.name)/'ledger'; home.mkdir(mode=0o700)
        self.row['events']={'uncertain':{'state':'sending'}}
        file=home/'state.json'; file.write_text(json.dumps({'version':1,'requests':{'request':self.row}})); file.chmod(0o600)
        before=file.read_bytes(); output=io.StringIO()
        with patch.dict(os.environ,{'CHIEF_NOD_STATE_DIR':str(home)}), patch.object(self.nod.sys,'stdout',output), patch.object(self.nod,'call') as api:
            self.nod.acceptance_status(Namespace(request_id='request')); api.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['request_state'],'pending')
        self.assertEqual(file.read_bytes(),before); self.assertEqual(list(home.iterdir()),[file])

    def test_legacy_unissued_wrong_outcome_and_invalid_answer_fail_closed(self):
        for field,value in [('issuance',None),('request_id','other'),('issuer',{'session':'ses_lead','directory':'/lead'})]:
            saved=self.a[field]; self.a[field]=value
            with self.assertRaises(ValueError): self.projection()
            self.a[field]=saved
        self.a['outcome_id']='old'
        with self.assertRaises(ValueError): self.projection()
        self.a['outcome_id']='outcome'
        for answer in ({'id':'answer','option_id':'accept'}, {'id':'answer','option_id':'unknown','created_at':T1}, {'id':'answer','option_id':'accept','created_at':'2001-01-01T00:00:00Z'}):
            self.row['decision']['decision']=answer
            with self.assertRaises(ValueError): self.projection()

    def test_chief_gate_reused_before_any_real_effect_and_exact_options(self):
        from argparse import Namespace
        args=Namespace(accept_project='project',accept_outcome='outcome',reference='outcome report',file=None,channel='chief',image=None,recommended=None,recommendation=None,dry_run=False)
        card={'title':'Accept this outcome?','default':'Wait without acceptance.','recommended':'accept','options':[
            {'id':'accept','label':'Accept','description':'Accept the finished outcome.'},
            {'id':'not-yet','label':'Not yet','description':'Keep the outcome open.'}]}
        self.assertEqual(self.nod.acceptance_intent(args,card)['outcome_id'],'outcome')
        with patch.object(self.nod.sys,'stdin',io.StringIO(json.dumps(card))), patch.object(self.nod,'decision_sender',side_effect=ValueError('non-chief')) as gate, patch.object(self.nod,'call') as call, patch.object(self.nod,'state') as state:
            with self.assertRaises(ValueError): self.nod.ask(args)
            gate.assert_called_once(); call.assert_not_called(); state.assert_not_called()
        card['options'][0]['label']='Approve'
        with self.assertRaises(ValueError): self.nod.acceptance_intent(args,card)

    def test_durable_issuance_binding_and_no_delivery_offline(self):
        from argparse import Namespace
        args=Namespace(accept_project='project',accept_outcome='outcome',reference='outcome report',file=None,channel='chief',image=None,recommended=None,recommendation=None,dry_run=False)
        card={'title':'Accept this outcome?','default':'Wait without acceptance.','recommended':'accept','options':[
            {'id':'accept','label':'Accept','description':'Accept the finished outcome.'},
            {'id':'not-yet','label':'Not yet','description':'Keep the outcome open.'}]}
        origin={'session':'ses_chief','directory':'/chief','reference':'outcome report','limits':None}
        data={'version':1,'requests':{},'creates':{}}
        from contextlib import contextmanager
        @contextmanager
        def state(): yield data,lambda:None
        def bind(a,req): req['idempotency_key']='fixture'; return origin
        with patch.object(self.nod.sys,'stdin',io.StringIO(json.dumps(card))), patch.object(self.nod,'decision_sender',return_value=self.a['issuer']), patch.object(self.nod,'ask_binding',side_effect=bind), patch.object(self.nod,'state',state), patch.object(self.nod,'announce_tower'), patch.object(self.nod,'reconcile'), patch.object(self.nod,'call',return_value={'request_id':'request'}) as api, patch('builtins.print'):
            self.nod.ask(args)
        self.assertEqual(api.call_count,1)
        self.assertEqual([(o['id'],o['label']) for o in api.call_args.args[2]['options']],[('accept','Accept'),('not-yet','Not yet')])
        saved=data['requests']['request']
        self.assertEqual(saved['acceptance']['outcome_id'],'outcome')
        self.assertEqual(saved['acceptance']['issuance'],'chief-only-v1')
        self.assertEqual(data['creates']['fixture']['acceptance']['project_id'],'project')
        # Local intent time is not manufactured as actual Nod request creation time.
        with self.assertRaises(ValueError): self.nod.acceptance_projection('request',saved)


if __name__ == '__main__': unittest.main()
