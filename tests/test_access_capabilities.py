"""Central candidate contracts: no native access, launcher receipt or roster mutation."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from access_policy import compile_policy,fixture_binding,evaluate,milestone_admission,launch_acceptance,binding_acceptance,digest


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.model=json.loads((ROOT/'access/model.json').read_text())
        self.binding=fixture_binding(self.model,'lead')
        self.binding['ownMilestone']={'sessionID':'ses_fixturelead','agentID':'lead','directory':self.binding['location']}

    def test_exact_own_row_capability_is_not_roster_or_execution_authority(self):
        b=self.binding;c=compile_policy(self.model,b);caller=b['ownMilestone']
        enrollment={'sessionID':caller['sessionID'],'directory':caller['directory']}
        self.assertEqual(milestone_admission(self.model,b,caller,enrollment),'allow')
        for other in ({**caller,'sessionID':'ses_other'},{**caller,'agentID':'other'},{**caller,'directory':'/other'}):
            self.assertEqual(milestone_admission(self.model,b,other,enrollment),'deny')
        self.assertEqual(milestone_admission(self.model,b,caller,None),'deny')
        self.assertEqual(milestone_admission(self.model,b,caller,{**enrollment,'directory':'/other'}),'deny')
        self.assertEqual(evaluate(c,'docket_milestone','own')['effect'],'allow')
        for action,resource in [('docket_milestone','foreign'),('read',b['home']+'/.docket/lead-checkins.jsonl'),
            ('edit',b['home']+'/.docket/lead-checkins.jsonl'),('shell','python3 -m docket.milestone')]:
            self.assertEqual(evaluate(c,action,resource)['effect'],'deny')
        unbound={k:v for k,v in b.items() if k!='ownMilestone'}
        self.assertEqual(evaluate(compile_policy(self.model,unbound),'docket_milestone','own')['effect'],'deny')
        with self.assertRaises(ValueError):compile_policy(self.model,{**b,'role':'worker'})
        report=binding_acceptance(self.model,c);self.assertEqual(report['passed'],report['total'])

    def contract(self):
        return {'launcherID':'fixture-tool-launcher','sessionID':'ses_new','agentID':'writer',
                'model':{'providerID':'fixture','modelID':'explicit-choice','variant':'high'},
                'directory':'/fixture/project','sessionPolicyDigest':digest([]),'bindingDigest':digest(self.binding)}

    def test_generic_start_and_identity_mismatches_are_detected_but_never_native_proof(self):
        contract=self.contract()
        result=launch_acceptance(self.model,contract,{**contract,'method':'generic-session'})
        self.assertEqual(result['reason'],'outside-declared-launcher');self.assertFalse(result['nativeProof'])
        for key,value in [('sessionID','ses_other'),('agentID','other'),('directory','/other'),
                          ('sessionPolicyDigest','1'*64),('bindingDigest','2'*64),
                          ('model',dict(contract['model'],variant='medium'))]:
            result=launch_acceptance(self.model,contract,{**contract,key:value})
            self.assertEqual(result['reason'],'launch-identity-contract-mismatch')
            self.assertEqual(result['status'],'not-ready')

    def test_claimed_receipt_or_launched_boolean_cannot_supply_provenance(self):
        contract=self.contract()
        for observed in (None,dict(contract),{**contract,'launched':True,'receipt':'caller-provided'}):
            result=launch_acceptance(self.model,contract,observed)
            self.assertEqual(result['status'],'not-ready');self.assertIsNone(result['receiptAdapter'])
        c=compile_policy(self.model,{**self.binding,'launchContract':contract,'launchObservation':dict(contract)})
        report=binding_acceptance(self.model,c)
        self.assertLess(report['passed'],report['total'])
        self.assertEqual(launch_acceptance(self.model)['status'],'not-required')
        self.assertIsNone(self.model['specialistLaunch']['receiptAdapter'])
        bad=copy.deepcopy(contract);del bad['model']['variant']
        with self.assertRaises(ValueError):launch_acceptance(self.model,bad)


if __name__=='__main__':unittest.main()
