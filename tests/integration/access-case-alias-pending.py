"""Unresolved independent required-deny case; intentionally fails on aliasing volumes.

Not part of lexical source unit tests. No expectedFailure or casefold simulation:
production file-identity gate remains BLOCKED until native canonical identity is proved.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
KIT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(KIT/'scripts'))
from access_policy import compile_policy,evaluate,fixture_binding

class CaseAliasPending(unittest.TestCase):
    def test_same_protected_file_must_deny_both_spellings(self):
        model=json.loads((KIT/'access/model.json').read_bytes())
        with tempfile.TemporaryDirectory(prefix='access-case-') as temp:
            root=Path(temp).resolve();secret=root/'.env';secret.write_text('HARMLESS_REVIEW_SENTINEL\n')
            alias=root/'.ENV'
            if not alias.exists() or not alias.samefile(secret):self.skipTest('filesystem has no demonstrated case alias')
            b=fixture_binding(model,'worker');b.update(location=str(root),projectRoot=str(root),assignedRoots=[str(root)],ownedWrites=[],sharedOutputs=[])
            b['communication']['originDirectory']=str(root)
            c=compile_policy(model,b)
            self.assertFalse(c['fileIdentityProtection']['productionReady'])
            self.assertEqual(evaluate(c,'read',str(secret))['effect'],'deny')
            self.assertEqual(evaluate(c,'read',str(alias))['effect'],'deny')

if __name__=='__main__':unittest.main()
