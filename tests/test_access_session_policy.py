"""Offline role+session composition regressions; no native reads or mutations."""
import copy
import json
from pathlib import Path
import unittest
import test_access_install as fixtures
from access_install import dry_run,verify_bundle
from access_policy import binding_acceptance,compile_for_agent,compose_session_policy,digest,evaluate


class SessionPolicy(unittest.TestCase):
    setUp=fixtures.AccessInstall.setUp
    entry=fixtures.AccessInstall.entry

    def snapshot(self,e,rules):
        b=e['binding']
        return {'sessionID':b['communication']['originSession'],'agentID':'fixture-agent',
                'directory':b['location'],'rules':rules,'rulesDigest':digest(rules)}

    def effective(self,e):
        role,_=compile_for_agent(self.model,e['binding'],Path(e['roleFile']).read_text(),managed_baseline=e['managedBaseline'])
        return role,compose_session_policy(role,e['sessionPolicySnapshot'])

    def test_stale_blanket_read_deny_refuses_required_reads_and_preserves_sources(self):
        e=self.entry('worker');before=Path(e['roleFile']).read_bytes()
        e['sessionPolicySnapshot']=self.snapshot(e,[{'action':'read','resource':'*','effect':'deny'}])
        snapshot=copy.deepcopy(e['sessionPolicySnapshot']);role,effective=self.effective(e)
        result=binding_acceptance(self.model,effective)
        conflicts=[r for r in result['rows'] if not r['pass']]
        self.assertTrue(any(r['id'].startswith('required-read-') for r in conflicts))
        self.assertTrue(all(r['rule']=='session-override-0' and r['layer']=='session' for r in conflicts))
        with self.assertRaisesRegex(ValueError,'acceptance conflict'):dry_run(self.manifest,self.root/'bundle')
        self.assertFalse((self.root/'bundle').exists());self.assertEqual(Path(e['roleFile']).read_bytes(),before)
        self.assertEqual(e['sessionPolicySnapshot'],snapshot)
        self.assertEqual(evaluate(role,'read','access-check.txt')['effect'],'allow')

    def test_stale_secret_allow_overrides_role_deny_and_refuses_forbidden_access(self):
        e=self.entry('worker');e['sessionPolicySnapshot']=self.snapshot(e,[{'action':'read','resource':'*.env','effect':'allow'}])
        role,effective=self.effective(e)
        self.assertEqual(evaluate(role,'read','src/.env')['effect'],'deny')
        self.assertEqual(evaluate(effective,'read','src/.env')['effect'],'allow')
        row=next(r for r in binding_acceptance(self.model,effective)['rows'] if r['id']=='assigned-env')
        self.assertEqual((row['expected'],row['actual'],row['rule'],row['layer']),('deny','allow','session-override-0','session'))
        with self.assertRaisesRegex(ValueError,'assigned-env'):dry_run(self.manifest,self.root/'bundle')
        self.assertFalse(effective['fileIdentityProtection']['productionReady']);self.assertIsNone(effective['run']['selected'])
        e['sessionPolicySnapshot']=self.snapshot(e,[{'action':'read','resource':'.env','effect':'allow'}])
        _,effective=self.effective(e)
        row=next(r for r in binding_acceptance(self.model,effective)['rows'] if r['id']=='session-literal-forbidden-0')
        self.assertEqual(row['actual'],'allow');self.assertFalse(row['pass'])
        with self.assertRaisesRegex(ValueError,'session-literal-forbidden'):dry_run(self.manifest,self.root/'bundle')

    def test_order_raw_snapshot_artifact_and_unknown_denials_survive(self):
        e=self.entry('worker')
        rules=[{'action':'read','resource':'src/main.py','effect':effect} for effect in ('deny','allow','deny')]
        rules.append({'action':'read','resource':'$HOME/.chief-of-staff/research/private.txt','effect':'ask'})
        e['sessionPolicySnapshot']=self.snapshot(e,rules);original=copy.deepcopy(e['sessionPolicySnapshot'])
        role,effective=self.effective(e)
        self.assertEqual(evaluate(effective,'read','src/main.py')['id'],'session-override-2')
        self.assertEqual(evaluate(effective,'read',e['binding']['home']+'/.chief-of-staff/research/private.txt')['effect'],'ask')
        self.assertEqual(evaluate(effective,'read','src/private.md')['effect'],'deny')
        out=self.root/'bundle';receipt=dry_run(self.manifest,out);self.assertEqual(verify_bundle(out),receipt)
        stem=e['binding']['id'];saved=json.loads((out/(stem+'.effective-policy.json')).read_bytes())
        emitted=json.loads((out/(stem+'.agent.md')).read_text()[4:].split('\n---\n')[0])
        self.assertEqual(saved['sessionPolicySnapshot'],original)
        self.assertEqual(saved['nativeRules'][:len(role['nativeRules'])],role['nativeRules'])
        self.assertEqual(emitted['permissions'],role['nativeRules']) # never flatten session rules into the role
        self.assertEqual(receipt['roles'][0]['sessionPolicySnapshotDigest'],digest(original))
        acceptance=json.loads((out/(stem+'.acceptance.json')).read_bytes())
        self.assertEqual(acceptance['sessionOverrides']['status'],'explicit-snapshot-evaluated')
        self.assertEqual(acceptance['passed'],acceptance['total']);self.assertFalse(acceptance['nativeProof'])

    def test_identity_digest_and_rule_shape_conflicts_refuse_before_publication(self):
        e=self.entry('worker');valid=self.snapshot(e,[])
        for key,value in [('sessionID','ses_wrong'),('directory',str(self.root)),('rulesDigest','0'*64),
                          ('agentID','bad agent'),('rules',[{'action':'read','resource':'*','effect':'bogus'}])]:
            with self.subTest(key=key):
                e['sessionPolicySnapshot']={**valid,key:value}
                with self.assertRaises(ValueError):dry_run(self.manifest,self.root/'bundle')
                self.assertFalse((self.root/'bundle').exists())
        e['sessionPolicySnapshot']=valid;e['observerIdentity']={'sessionID':valid['sessionID'],'agentID':'different'}
        with self.assertRaisesRegex(ValueError,'observer identity differ'):dry_run(self.manifest,self.root/'bundle')


if __name__=='__main__':unittest.main()
