"""Temporary personal plans only. No host/API requests or installed policy edits."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from access_policy import compile_policy, fixture_binding, evaluate, binding_acceptance, checkbox_admission
from project_plan_binding import bind_project_plans


class ProjectPlans(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve()
        self.model=json.loads((ROOT/'access/model.json').read_text())
        self.b=fixture_binding(self.model,'lead');self.b['home']=str(self.home)
        self.b['communication']['chiefPointer']=str(self.home/'.chief-of-staff/chief.json')
        self.b['sharedOutputs']=[]
        self.root=self.home/'.config/openchamber/projects/fixture-owner/plans'
        self.root.mkdir(parents=True)
        self.file=self.root/'approved.md';self.file.write_text('# Plan\n\n## Steps\n- [ ] Verify\n\nKeep all constraints.\n')
        self.before=self.file.read_bytes()
        self.session={'id':self.b['communication']['originSession'],'agent':'lead','location':{'directory':self.b['location']}}
        self.project={'sessionID':self.session['id'],'directory':self.b['location'],'projectId':'fixture-owner','plansRoot':str(self.root)}
        self.knowledge={'projectId':'fixture-owner','plans':[{'id':'plan-own','source':'personal','path':str(self.file)}]}

    def bind(self):return bind_project_plans(self.b,self.session,self.project,self.knowledge)

    def test_exact_own_files_and_external_gate_only_no_metadata_foreign_or_unlisted_grant(self):
        c=compile_policy(self.model,self.bind())
        for action in ('read','edit'):self.assertEqual(evaluate(c,action,str(self.file))['effect'],'allow')
        for file in (self.root/'unlisted.md',self.root.parent/'context.json',self.root.parent.parent/'foreign/plans/approved.md',self.home/'.config/openchamber/settings.json'):
            self.assertEqual(evaluate(c,'edit',str(file))['effect'],'deny')
        self.assertEqual(evaluate(c,'openchamber_knowledge','*')['effect'],'deny')
        self.assertFalse(c['installable']);self.assertIsNone(self.model['runSelection'])
        report=binding_acceptance(self.model,c);self.assertEqual(report['passed'],report['total'])
        self.assertEqual(self.file.read_bytes(),self.before)

    def test_session_project_location_and_project_id_spoof_refused(self):
        for field,value in [('sessionID','ses_foreign'),('directory','/foreign'),('projectId','foreign'),('plansRoot',str(self.home))]:
            project={**self.project,field:value}
            with self.assertRaises(ValueError):bind_project_plans(self.b,self.session,project,self.knowledge)
        for session in ({**self.session,'id':'ses_foreign'},{**self.session,'agent':'worker'},
                        {**self.session,'location':{'directory':'/foreign'}},{**self.session,'time':{'archived':1}}):
            with self.assertRaises(ValueError):bind_project_plans(self.b,session,self.project,self.knowledge)

    def test_foreign_shared_traversal_duplicate_and_symlink_plan_refused(self):
        for change in ({'source':'shared'},{'path':str(self.root.parent/'foreign.md')},
                       {'path':str(self.root)+'/../foreign.md'}):
            knowledge=copy.deepcopy(self.knowledge);knowledge['plans'][0].update(change)
            with self.assertRaises(ValueError):bind_project_plans(self.b,self.session,self.project,knowledge)
        self.knowledge['plans']*=2
        with self.assertRaises(ValueError):self.bind()
        self.knowledge['plans']=self.knowledge['plans'][:1]
        real=self.root/'real.md';self.file.rename(real);self.file.symlink_to(real)
        with self.assertRaises(ValueError):self.bind()
        self.file.unlink();os.link(real,self.file)
        with self.assertRaises(ValueError):self.bind()

    def test_symlink_ancestor_refused(self):
        moved=self.root.with_name('real-plans');self.root.rename(moved);self.root.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(ValueError):self.bind()

    def test_unbound_and_stricter_custom_denial_remain_denied(self):
        self.assertEqual(evaluate(compile_policy(self.model,self.b),'edit',str(self.file))['effect'],'deny')
        c=compile_policy(self.model,self.bind(),custom_denies=[{'action':'edit','resource':str(self.file),'effect':'deny'}])
        self.assertEqual(evaluate(c,'edit',str(self.file))['effect'],'deny')
        report=binding_acceptance(self.model,c);self.assertLess(report['passed'],report['total'])
        bad=self.bind();bad['projectPlans']['files']=[str(self.root.parent/'context.json')]
        with self.assertRaises(ValueError):compile_policy(self.model,bad)

    def test_checkbox_capability_does_not_enable_file_or_knowledge_edits(self):
        caller={'sessionID':self.session['id'],'agentID':'lead','directory':self.b['location']}
        b={**self.b,'planCheckbox':{**caller,'planIDs':['plan-own']}}
        c=compile_policy(self.model,b)
        self.assertEqual(evaluate(c,'plan_checkbox','own')['effect'],'allow')
        for action,target in [('plan_checkbox','foreign'),('edit',str(self.file)),('openchamber_knowledge','*'),('shell','*')]:
            self.assertEqual(evaluate(c,action,target)['effect'],'deny')
        self.assertEqual(checkbox_admission(self.model,b,caller,'plan-own'),'allow')
        self.assertEqual(checkbox_admission(self.model,b,caller,'foreign'),'deny')
        self.assertEqual(checkbox_admission(self.model,b,{**caller,'sessionID':'ses_foreign'},'plan-own'),'deny')
        stricter=compile_policy(self.model,b,custom_denies=[{'action':'plan_checkbox','resource':'*','effect':'deny'}])
        self.assertEqual(evaluate(stricter,'plan_checkbox','own')['effect'],'deny')
        with self.assertRaises(ValueError):compile_policy(self.model,{**b,'role':'worker'})


if __name__=='__main__':unittest.main()
