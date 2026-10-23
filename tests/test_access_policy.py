"""Non-live compiler/matrix tests: synthetic roots, no host, no installed writes."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from access_policy import compile_policy, compile_for_agent, amend_agent, evaluate, fixture_binding, matrix, matrix_document, wildcard


class AccessPolicy(unittest.TestCase):
    def setUp(self):
        self.model=json.loads((ROOT/'access/model.json').read_text())
        self.binding=fixture_binding(self.model,'worker')

    def test_all_roles_use_one_matrix_and_unselected_run_profile(self):
        rows=matrix(self.model)
        self.assertEqual(len(rows),8*len(self.model['matrix']))
        self.assertTrue(all(r['pass'] for r in rows),[r for r in rows if not r['pass']])
        for role in self.model['roles']:
            c=compile_policy(self.model,fixture_binding(self.model,role))
            self.assertTrue(c['candidateOnly']);self.assertFalse(c['installable'])
            self.assertIsNone(c['run']['selected'])
            self.assertEqual(c['modelDigest'],compile_policy(self.model,self.binding)['modelDigest'])
            self.assertEqual(len(c['ruleManifest']),len({r['id'] for r in c['ruleManifest']}))
            self.assertTrue(all(set(r)=={'action','resource','effect'} for r in c['nativeRules']))
            self.assertIn('read',c['toolVisibilityCandidate'])
            if role=='dispatcher':
                self.assertIn('heartbeat_resolve',c['toolVisibilityCandidate'])
                self.assertNotIn('patch',c['toolVisibilityCandidate'])

    def test_generated_matrix_is_current_not_a_second_policy(self):
        self.assertEqual(matrix_document(self.model),json.loads((ROOT/'access/matrix.json').read_text()))

    def test_literal_binding_validation_no_cwd_or_unknown_role_inference(self):
        for update in ({'assignedRoots':[]},{'assignedRoots':['/fixture/home']},{'role':'invented-specialist'}, {'ownedWrites':[{'path':'/elsewhere/result','kind':'file'}]},
                       {'assignedRoots':['/fixture/*']},{'ownedWrites':[{'path':'/fixture/home','kind':'directory'}]},
                       {'sharedOutputs':[{'path':'/unassigned/recipient/result.md','kind':'file'}]}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                compile_policy(self.model,{**self.binding,**update})
        incomplete=dict(self.binding);del incomplete['home']
        with self.assertRaises(ValueError):compile_policy(self.model,incomplete)
        with self.assertRaises(ValueError):compile_policy(self.model,fixture_binding(self.model,'dispatcher') | {'ownedWrites':[{'path':'/fixture/project/result','kind':'file'}]})

    def test_file_write_scope_does_not_become_directory_or_shared_read_write(self):
        c=compile_policy(self.model,self.binding)
        for p in ('owned/result.md','/fixture/project/owned/result.md','./owned/../owned/result.md'):
            self.assertEqual(evaluate(c,'edit',p)['effect'],'allow')
        for p in ('owned/result.md/child','owned/other.md','../elsewhere.md','/fixture/home/_skills/file.md'):
            self.assertEqual(evaluate(c,'edit',p)['effect'],'deny')

    def test_internal_wildcard_does_not_escape_to_sibling_or_external_read_only_root(self):
        b={**self.binding,'location':'/fixture/project/wt/task',
           'assignedRoots':['/fixture/project/wt/task'],
           'ownedWrites':[{'path':'/fixture/project/wt/task','kind':'directory'}]}
        b['communication']={**b['communication'],'originDirectory':b['location']}
        c=compile_policy(self.model,b)
        self.assertEqual(evaluate(c,'edit','src/main.py')['effect'],'allow')
        for p in ('../neighbor/main.py','../../root.md','/fixture/home/_skills/SKILL.md',
                  '/fixture/home/.chief-of-staff/research/result.md'):
            self.assertEqual(evaluate(c,'edit',p)['effect'],'deny',p)
        for p in ('../neighbor/private.md','../../root.md','/fixture/project/wt/neighbor/private.md'):
            self.assertEqual(evaluate(c,'read',p)['effect'],'deny',p)
        self.assertEqual(evaluate(c,'read','/fixture/home/_skills/SKILL.md')['effect'],'allow')

    def test_explicit_ancestor_assignment_and_sibling_restore_only_the_bound_union(self):
        b={**self.binding,'location':'/fixture/project/wt/task','assignedRoots':['/fixture/project'],
           'ownedWrites':[{'path':'/fixture/project/wt/task','kind':'directory'}],
           'recipientRoots':['/fixture/project/recipient'],
           'sharedOutputs':[{'path':'/fixture/project/recipient/result.md','kind':'file'}]}
        b['communication']={**b['communication'],'originDirectory':b['location']}
        c=compile_policy(self.model,b)
        self.assertEqual(evaluate(c,'read','../../src/main.py')['effect'],'allow')
        self.assertEqual(evaluate(c,'edit','../../recipient/result.md')['effect'],'allow')
        self.assertEqual(evaluate(c,'edit','../../recipient/other.md')['effect'],'deny')
        self.assertEqual(evaluate(c,'read','../../../other-project/private.md')['effect'],'deny')

    def test_chief_relative_resources_and_protected_root_overrides(self):
        b={**fixture_binding(self.model,'chief'),'location':'/fixture/home/.chief-of-staff','projectRoot':'/fixture/home/.chief-of-staff',
           'assignedRoots':['/fixture/home/.chief-of-staff'],
           'ownedWrites':[{'path':'/fixture/home/.chief-of-staff/research','kind':'directory'}]}
        b['communication']={**b['communication'],'originDirectory':b['location']}
        c=compile_policy(self.model,b)
        for p in ('research/result.md','./research/result.md','/fixture/home/.chief-of-staff/research/result.md'):
            self.assertEqual(evaluate(c,'edit',p)['effect'],'allow')
        for action in ('read','edit'):
            for p in ('secrets/sentinel','/fixture/home/.chief-of-staff/secrets/sentinel','research/nested/.env'):
                self.assertEqual(evaluate(c,action,p)['effect'],'deny')

    def test_run_classifications_are_explicit_but_never_activated(self):
        for requested in self.model['runProfiles']:
            c=compile_policy(self.model,{**self.binding,'runProfile':requested})
            self.assertEqual(c['run']['requested'],requested)
            self.assertIsNone(c['run']['selected']);self.assertFalse(c['installable'])
            for tool in ('shell','execute','grep','glob','subagent'):
                self.assertEqual(evaluate(c,tool,'*')['effect'],'deny')

    def test_json_custom_prompt_and_metadata_preserved_stricter_denials_retained(self):
        body='Full custom writer prompt.\n\nNo rewritten voice or hidden include.\n'
        fields={'description':'Customized','mode':'primary','model':'keep-model','steps':6,
                'permissions':[{'action':'*','resource':'*','effect':'deny'},
                               {'action':'read','resource':'/fixture/home/.chief-of-staff/research/private/*','effect':'deny'}]}
        text='---\n'+json.dumps(fields)+'\n---\n'+body
        with self.assertRaises(ValueError):amend_agent(text,compile_policy(self.model,self.binding))
        baseline=[fields['permissions'][0]]
        c,emitted=compile_for_agent(self.model,self.binding,text,managed_baseline=baseline);header,newbody=emitted[4:].split('\n---\n',1)
        after=json.loads(header)
        self.assertEqual(newbody,body)
        self.assertEqual({k:v for k,v in after.items() if k!='permissions'},{k:v for k,v in fields.items() if k!='permissions'})
        self.assertEqual(evaluate(c,'read','/fixture/home/.chief-of-staff/research/private/no.md')['effect'],'deny')
        self.assertEqual(compile_for_agent(self.model,self.binding,text,managed_baseline=baseline)[1],emitted)
        self.assertEqual(compile_for_agent(self.model,self.binding,emitted)[1],emitted)

    def test_standard_yaml_metadata_and_body_preserved_without_general_yaml_guessing(self):
        text='---\ndescription: Lead.\nmode: primary\npermissions:\n  - action: edit\n    resource: "*"\n    effect: deny\nmodel: keep-model\n---\nExact custom body\n'
        c,emitted=compile_for_agent(self.model,self.binding,text)
        self.assertTrue(emitted.startswith('---\ndescription: Lead.\nmode: primary\n'))
        self.assertIn('\nmodel: keep-model\n---\nExact custom body\n',emitted)
        self.assertEqual(evaluate(c,'edit','owned/result.md')['effect'],'deny')
        with self.assertRaises(ValueError):
            compile_for_agent(self.model,self.binding,'---\npermissions:\n  - <<: *anchor\n---\nBody')

    def test_unknown_blanket_custom_denials_are_not_silently_retired(self):
        rules=[{'action':'*','resource':'*','effect':'deny'}]
        text='---\n'+json.dumps({'permissions':rules})+'\n---\nCustom body\n'
        c,_=compile_for_agent(self.model,self.binding,text)
        self.assertEqual(evaluate(c,'read','src/main.py')['effect'],'deny')
        self.assertEqual(c['retainedCustomDenials'],rules)
        c,_=compile_for_agent(self.model,self.binding,text,managed_baseline=rules)
        self.assertEqual(evaluate(c,'read','src/main.py')['effect'],'allow')

    def test_reporting_origin_and_tools_agree_without_claiming_native_availability(self):
        for role in ('lead','writer','shaping','research','specialist'):
            b=fixture_binding(self.model,role);c=compile_policy(self.model,b)
            route=c['communication'];bus=route['requiredBusBinding']
            self.assertEqual(bus['originSessions'],[b['communication']['originSession']])
            self.assertEqual(bus['originDirectories'],{b['communication']['originSession']:b['location']})
            self.assertIn('chief_post',c['toolVisibilityCandidate'])
            self.assertEqual(evaluate(c,'chief_post','*')['effect'],'allow')
            self.assertEqual(route['toolAvailability'],'unverified');self.assertFalse(route['nativeProof'])
            self.assertEqual(evaluate(c,'openchamber','*')['effect'],'deny')
        c=compile_policy(self.model,self.binding)
        self.assertEqual(c['communication']['target'],'parent')
        self.assertNotIn('chief_post',c['toolVisibilityCandidate'])
        self.assertEqual(evaluate(c,'chief_post','*')['effect'],'deny')
        b=copy.deepcopy(self.binding);b['communication']['transport']='chief-post'
        with self.assertRaises(ValueError):compile_policy(self.model,b)
        b=copy.deepcopy(self.binding);b['communication']['originDirectory']='/fixture/other'
        with self.assertRaises(ValueError):compile_policy(self.model,b)
        b=copy.deepcopy(self.binding);del b['communication']
        self.assertEqual(compile_policy(self.model,b)['communication']['status'],'unbound-no-reporting-route')

    def test_chief_inbox_is_an_exact_output_not_arbitrary_inbox_or_pointer_mutation(self):
        b=fixture_binding(self.model,'writer');pointer=b['communication']['chiefPointer']
        inbox='/fixture/home/.chief-of-staff/inbox/fixture-report.md'
        b['communication'].update(transport='chief-inbox',inboxOutput=inbox)
        b['sharedOutputs'].append({'path':inbox,'kind':'file'})
        c=compile_policy(self.model,b)
        self.assertEqual(evaluate(c,'read',pointer)['effect'],'allow')
        self.assertEqual(evaluate(c,'edit',pointer)['effect'],'deny')
        self.assertEqual(evaluate(c,'edit',inbox)['effect'],'allow')
        self.assertEqual(evaluate(c,'edit',inbox+'-other')['effect'],'deny')
        self.assertNotIn('chief_post',c['toolVisibilityCandidate'])
        b['communication']['chiefPointer']='/fixture/fake-chief.json'
        with self.assertRaises(ValueError):compile_policy(self.model,b)

    def test_native_wildcards_not_fnmatch_brackets_and_last_match(self):
        self.assertTrue(wildcard('a/b/c','a/*'))
        self.assertTrue(wildcard('git status','git status *'))
        self.assertTrue(wildcard('git status --short','git status *'))
        self.assertFalse(wildcard('a','[ab]'))
        c=compile_policy(self.model,self.binding,custom_denies=[{'action':'read','resource':'src/private.md','effect':'deny'}])
        self.assertEqual(evaluate(c,'read','src/private.md')['reason'],'custom-stricter-deny')


if __name__=='__main__':unittest.main()
