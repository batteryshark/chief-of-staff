"""Installer candidate safety expectations; owned files only, no host or live policies."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from access_install import dry_run,verify_bundle,activate,sha,body_bytes
from access_policy import MODEL,evaluate,fixture_binding,compile_for_agent


class AccessInstall(unittest.TestCase):
    # Independent review cases adopted without weakening their required outcomes.
    def test_review_blocked_inbox_pointer_output_and_required_read_refuse(self):
        for role,action,resource in [('writer','edit','*'),('lead','read','pointer'),('worker','read','*')]:
            with self.subTest(role=role):
                e=self.entry(role);b=e['binding'];source=Path(e['roleFile'])
                if role!='worker':
                    output=b['home']+'/.chief-of-staff/inbox/own-report.md'
                    b['sharedOutputs']=[{'path':output,'kind':'file'}]
                    b['communication'].update(transport='chief-inbox',inboxOutput=output)
                rule={'action':action,'resource':b['communication']['chiefPointer'] if resource=='pointer' else resource,'effect':'deny'}
                fields=json.loads(source.read_text()[4:].split('\n---\n')[0]);fields['permissions'].append(rule)
                source.write_text('---\n'+json.dumps(fields)+'\n---\nExact custom body.\n');e['beforeSha256']=sha(source.read_bytes())
                with self.assertRaisesRegex(ValueError,'acceptance conflict'):dry_run({'roles':[e]},self.root/('blocked-'+role))
                self.assertIn(rule,json.loads(source.read_text()[4:].split('\n---\n')[0])['permissions'])

    def test_review_changed_generation_requires_provenance(self):
        b=fixture_binding(self.model,'worker');original='---\n{"permissions":[]}\n---\nExact custom body.\n'
        _,emitted=compile_for_agent(self.model,b,original)
        revised=copy.deepcopy(self.model);revised['commonReads'].append({'id':'approved-added-handoff','path':'/fixture/approved-handoff'})
        with self.assertRaisesRegex(ValueError,'provenance'):compile_for_agent(revised,b,emitted)
        changed=copy.deepcopy(b);changed['assignedRoots'].append('/fixture/extra')
        with self.assertRaisesRegex(ValueError,'provenance'):compile_for_agent(self.model,changed,emitted)

    def test_review_home_expansion_and_indentless_yaml(self):
        b=fixture_binding(self.model,'writer')
        for prefix in ('$HOME/','~/'):
            for action in ('read','external_directory'):
                rule={'action':action,'resource':prefix+'.chief-of-staff/research/*','effect':'deny'}
                text='---\n'+json.dumps({'permissions':[rule]})+'\n---\nExact custom body.\n'
                c,emitted=compile_for_agent(self.model,b,text)
                self.assertEqual(evaluate(c,'read',b['home']+'/.chief-of-staff/research/result.md')['effect'],'deny')
                self.assertTrue(emitted.endswith('Exact custom body.\n'))
        text='---\ndescription: Custom\npermissions:\n- action: read\n  resource: "*"\n  effect: deny\nmodel: keep\n---\nCustom body.\n'
        with self.assertRaisesRegex(ValueError,'indentless'):compile_for_agent(self.model,b,text)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='access-install-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.home=self.root/'home';self.home.mkdir()
        self.parent=self.root/'parent';self.parent.mkdir()
        self.agents=self.root/'agents';self.agents.mkdir()
        self.model=json.loads(MODEL.read_bytes());self.manifest={'roles':[]}
        self.baseline={'action':'*','resource':'*','effect':'deny'}

    def entry(self,role='writer'):
        project=self.root/('project-'+role);project.mkdir()
        b=fixture_binding(self.model,role)
        b.update(home=str(self.home),location=str(project),projectRoot=str(project),assignedRoots=[str(project)])
        b['ownedWrites']=([{'path':str(project/'owned/result.md'),'kind':'file'}] if self.model['roles'][role]['writes'] else [])
        b['sharedOutputs']=([{'path':str(self.home/'.chief-of-staff/handoff/result.md'),'kind':'file'}] if self.model['roles'][role]['writes'] else [])
        b['communication']['originDirectory']=str(project)
        if 'chiefPointer' in b['communication']:b['communication']['chiefPointer']=str(self.home/'.chief-of-staff/chief.json')
        if 'parentDirectory' in b['communication']:b['communication']['parentDirectory']=str(self.parent)
        source=self.agents/(role+'.md')
        fields={'description':'Custom role','model':'KEEP_MODEL','mode':'primary','permissions':[self.baseline,
            {'action':'read','resource':'src/private.md','effect':'deny'}]}
        text='---\n'+json.dumps(fields)+'\n---\nExact custom π prompt\n\nNo rewritten includes.\n'
        source.write_bytes(text.encode())
        e={'binding':b,'agentRoot':str(self.agents),'roleFile':str(source),'beforeSha256':sha(source.read_bytes()),'managedBaseline':[self.baseline]}
        self.manifest['roles'].append(e);return e

    def test_all_roles_permission_only_and_reporting_visibility_with_unchanged_sources(self):
        for role in self.model['roles']:self.entry(role)
        before={e['roleFile']:Path(e['roleFile']).read_bytes() for e in self.manifest['roles']}
        out=self.root/'bundle';r=dry_run(self.manifest,out)
        self.assertIsNone(r['runSelected']);self.assertFalse(r['installable'])
        self.assertEqual(verify_bundle(out),r)
        visibility=json.loads((out/'visibility.json').read_bytes())
        self.assertEqual({v['role'] for v in visibility},set(self.model['roles']))
        for e in self.manifest['roles']:
            b=e['binding'];policy=json.loads((out/(b['id']+'.policy.json')).read_bytes())
            emitted=(out/(b['id']+'.agent.md')).read_bytes();original=before[e['roleFile']]
            self.assertEqual(Path(e['roleFile']).read_bytes(),original)
            self.assertEqual(body_bytes(emitted),body_bytes(original));self.assertIsNone(policy['run']['selected'])
            acceptance=json.loads((out/(b['id']+'.acceptance.json')).read_bytes())
            self.assertEqual(acceptance['passed'],acceptance['total'])
            self.assertFalse(acceptance['nativeProof'])
            self.assertFalse(acceptance['fileIdentityProtection']['productionReady'])
            old=json.loads(original.decode()[4:].split('\n---\n')[0]);new=json.loads(emitted.decode()[4:].split('\n---\n')[0])
            self.assertEqual({k:v for k,v in old.items() if k!='permissions'},{k:v for k,v in new.items() if k!='permissions'})
            # Independently named required negative outcomes, not matrix-generated expectations.
            for action,target in [('read',b['location']+'/.env'),('read',str(self.home/'.chief-of-staff/secrets/fixture')),
                                  ('read',str(self.home/'Library/Keychains/fixture')),('read',b['location']+'/src/private.md'),
                                  ('edit',b['location']+'/unowned.md'),('read',str(self.root/'unassigned/file.md'))]:
                self.assertEqual(evaluate(policy,action,target)['effect'],'deny',(b['role'],action,target))
            self.assertEqual(evaluate(policy,'read',b['location']+'/src/ordinary.md')['effect'],'allow')
            self.assertEqual(evaluate(policy,'shell','python3 tests.py')['effect'],'deny')
            self.assertEqual(evaluate(policy,'a2a_send','*')['effect'],'deny')
            v=next(v for v in visibility if v['role']==b['role'])
            self.assertEqual(v['nativeToolPresence'],'unverified')
            if b['role'] in ('lead','writer','shaping','research','specialist'):
                self.assertIn('chief_post',v['tools'])
                self.assertEqual(v['communication']['requiredBusBinding']['originDirectories'],{b['communication']['originSession']:b['location']})
            if b['role']=='worker':
                self.assertNotIn('chief_post',v['tools']);self.assertEqual(v['communication']['target'],'parent')
            if b['role']=='chief':
                self.assertTrue({'heartbeat_close','heartbeat_status','heartbeat_reconcile'}<=set(v['tools']))
            if b['role']=='dispatcher':
                self.assertEqual(set(v['tools']),{'read','heartbeat_resolve'})
        self.assertEqual((out/'receipt.json').stat().st_mode&0o777,0o400)
        self.assertEqual(r['knownSessionMigration'],'not-generated-no-native-calls')

    def test_before_hash_conflict_refuses_without_bundle_or_target_write(self):
        e=self.entry();source=Path(e['roleFile']);source.write_bytes(source.read_bytes()+b'Owner edit\n')
        with self.assertRaisesRegex(ValueError,'before-hash conflict'):dry_run(self.manifest,self.root/'bundle')
        self.assertFalse((self.root/'bundle').exists());self.assertTrue(source.read_bytes().endswith(b'Owner edit\n'))

    def test_create_only_receipt_and_later_source_conflict(self):
        e=self.entry();out=self.root/'bundle';dry_run(self.manifest,out);receipt=(out/'receipt.json').read_bytes()
        with self.assertRaises(ValueError):dry_run(self.manifest,out)
        self.assertEqual((out/'receipt.json').read_bytes(),receipt)
        Path(e['roleFile']).write_bytes(Path(e['roleFile']).read_bytes()+b'Changed\n')
        with self.assertRaisesRegex(ValueError,'before-hash conflict'):verify_bundle(out)
        receipt_file=out/'receipt.json';receipt_file.rename(out/'retained-receipt.json');receipt_file.symlink_to(out/'retained-receipt.json')
        with self.assertRaisesRegex(ValueError,'symlink'):verify_bundle(out)

    def test_symlink_assigned_root_and_missing_explicit_root_refuse(self):
        e=self.entry();alias=self.root/'alias';alias.symlink_to(e['binding']['location'],target_is_directory=True)
        e['binding']['ownedWrites']=[]
        e['binding']['assignedRoots']=[str(alias)]
        with self.assertRaisesRegex(ValueError,'symlink'):dry_run(self.manifest,self.root/'bundle')
        e['binding']['assignedRoots']=[str(self.root/'missing')]
        with self.assertRaisesRegex(ValueError,'missing'):dry_run(self.manifest,self.root/'bundle')

    def test_symlink_owned_output_ancestor_and_source_refuse(self):
        e=self.entry();owned=Path(e['binding']['location'])/'owned';owned.symlink_to(self.parent,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):dry_run(self.manifest,self.root/'bundle')
        owned.unlink();source=Path(e['roleFile']);bytes_=source.read_bytes();source.unlink()
        target=self.root/'actual.md';target.write_bytes(bytes_);source.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'symlink'):dry_run(self.manifest,self.root/'bundle')

    def test_root_identity_change_and_candidate_tamper_refuse(self):
        e=self.entry();out=self.root/'bundle';dry_run(self.manifest,out)
        project=Path(e['binding']['location']);project.rename(self.root/'retained-old-root');project.mkdir()
        with self.assertRaisesRegex(ValueError,'identity changed'):verify_bundle(out)
        candidate=out/(e['binding']['id']+'.agent.md');candidate.chmod(0o600);candidate.write_bytes(b'not an agent')
        with self.assertRaisesRegex(ValueError,'before-hash conflict'):verify_bundle(out)

    def test_custom_ask_or_reporting_deny_not_silently_widened(self):
        e=self.entry();source=Path(e['roleFile']);raw=source.read_text();fields=json.loads(raw[4:].split('\n---\n')[0])
        fields['permissions'].append({'action':'chief_post','resource':'*','effect':'deny'})
        source.write_text('---\n'+json.dumps(fields)+'\n---\nCustom\n');e['beforeSha256']=sha(source.read_bytes())
        with self.assertRaisesRegex(ValueError,'blocks reporting'):dry_run(self.manifest,self.root/'bundle')
        fields['permissions'][-1]['effect']='ask';source.write_text('---\n'+json.dumps(fields)+'\n---\nCustom\n');e['beforeSha256']=sha(source.read_bytes())
        with self.assertRaisesRegex(ValueError,'ask constraints'):dry_run(self.manifest,self.root/'bundle')

    def test_activation_missing_binding_and_watched_outputs_always_refuse(self):
        e=self.entry()
        with self.assertRaisesRegex(ValueError,'ACTIVATION REFUSED'):activate(self.root/'bundle')
        with self.assertRaisesRegex(ValueError,'installed agent root'):dry_run(self.manifest,self.agents/'bundle')
        b=copy.deepcopy(e['binding']);del e['binding']['communication']
        with self.assertRaisesRegex(ValueError,'reporting route missing'):dry_run(self.manifest,self.root/'bundle')
        e['binding']=b;e['binding']['runProfile']='trusted-host'
        out=self.root/'bundle';r=dry_run(self.manifest,out);self.assertIsNone(r['runSelected'])
        with self.assertRaisesRegex(ValueError,'ACTIVATION REFUSED'):activate(out)

    def test_observer_sidecar_is_disabled_and_requires_explicit_agent_origin(self):
        e=self.entry();e['observerIdentity']={'sessionID':e['binding']['communication']['originSession'],'agentID':'exact-writer'}
        out=self.root/'bundle';dry_run(self.manifest,out)
        observer=json.loads((out/'observers.json').read_bytes())[0]
        self.assertFalse(observer['enabled']);self.assertTrue(observer['singleWriterRequired'])
        self.assertEqual(observer['bindings'][0]['agentID'],'exact-writer')
        self.assertEqual(observer['bindings'][0]['compilation']['binding']['location'],e['binding']['location'])
        self.assertEqual(observer['bindings'][0]['publicPaths'],[])
        self.assertIsNone(observer['bindings'][0]['compilation']['run']['selected'])
        e['observerIdentity']['sessionID']='ses_wrong'
        with self.assertRaisesRegex(ValueError,'observer identity'):dry_run(self.manifest,self.root/'bad-bundle')


if __name__=='__main__':unittest.main()
