"""Private durable options, synthetic values only; no cards, credentials or state reads."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import render


class NodOptionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.brief=self.root/'brief'; self.brief.mkdir(mode=0o700)
        self.script=self.root/'chief_nod.py'; self.script.write_text(render.render('scripts/chief-nod',str(self.brief)))
        spec=importlib.util.spec_from_file_location('nod_options_fixture',self.script)
        self.nod=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.nod)
        self.input=self.root/'local-nod-options.json'
        self.value={'version':1,'url':'http://nod.example.invalid:8767','image_base':'https://images.example.invalid/cards','retired_sessions':['ses_synthetic_retired']}

    def input_file(self,value=None):
        self.input.write_text(json.dumps(self.value if value is None else value)); self.input.chmod(0o600)

    def configure(self,absent=True,expected=None):
        args=argparse.Namespace(file=str(self.input),expect_absent=absent,expect_sha256=expected)
        with patch.object(self.nod,'call') as api, patch.object(self.nod,'state') as state, patch('builtins.print'):
            result=self.nod.configure(args)
            api.assert_not_called(); state.assert_not_called()
        return result

    def test_actual_rendered_cli_persists_values_for_isolated_ordinary_call(self):
        self.input_file()
        env={'PATH':os.environ.get('PATH',''),'HOME':str(self.root)}
        result=subprocess.run([sys.executable,'-B',str(self.script),'configure',str(self.input),'--expect-absent'],env=env,capture_output=True,text=True,check=True)
        self.assertIn('configured local Nod options',result.stdout)
        help_result=subprocess.run([sys.executable,'-B',str(self.script),'configure','--help'],env=env,capture_output=True,text=True,check=True)
        for signifier in ('--expect-absent','--expect-sha256','Example:','No card is sent'):
            self.assertIn(signifier,help_result.stdout)
        probe='import runpy,json,sys; n=runpy.run_path(sys.argv[1]); print(json.dumps([n["base_url"](),n["local_options"]()["image_base"],sorted(n["retired_chiefs"]())]))'
        isolated=subprocess.run([sys.executable,'-B','-c',probe,str(self.script)],env=env,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(isolated.stdout),[self.value['url'],self.value['image_base'],self.value['retired_sessions']])
        self.assertEqual(self.nod.options_path().stat().st_mode & 0o777,0o600)
        for actual in (self.value['url'],self.value['image_base'],self.value['retired_sessions'][0]):
            self.assertNotIn(actual,self.script.read_text())
        self.assertFalse((self.brief/'nod-continuations').exists())

    def test_explicit_empty_fresh_set_not_an_imaginary_retired_identity(self):
        value=dict(self.value,retired_sessions=[],image_base=''); self.input_file(value); self.configure()
        with patch.dict(os.environ,{'CHIEF_NOD_RETIRED_SESSION':'ses_unrelated_env','CHIEF_NOD_URL':'http://wrong.invalid'}):
            self.assertEqual(self.nod.retired_chiefs(),set())
            self.assertEqual(self.nod.base_url(),value['url'])
            with self.assertRaises(ValueError): self.nod.publish_image('/not-read.png',True)

    def test_migration_guards_preserved_missing_or_malformed_file_fails_closed(self):
        self.input_file(); self.configure()
        with patch.object(self.nod.shutil,'which') as native:
            with self.assertRaises(ValueError): self.nod.native_origin('ses_synthetic_retired')
            native.assert_not_called()
        before=self.nod.options_path().read_bytes(); expected=hashlib.sha256(before).hexdigest()
        self.input_file(dict(self.value,retired_sessions=[]))
        with self.assertRaises(ValueError): self.configure(False,expected)
        self.assertEqual(self.nod.options_path().read_bytes(),before)
        self.nod.options_path().write_text('{malformed')
        # Even an otherwise valid old environment cannot rescue a corrupt file.
        with patch.dict(os.environ,{'CHIEF_NOD_RETIRED_SESSION':'ses_synthetic_retired'}):
            with self.assertRaises(ValueError): self.nod.local_options()
        self.nod.options_path().unlink()
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError): self.nod.local_options()
        with patch.dict(os.environ,{'CHIEF_NOD_RETIRED_SESSION':'ses_synthetic_retired','CHIEF_NOD_URL':self.value['url']}):
            with self.assertRaises(ValueError): self.nod.local_options()

    def test_guarded_update_and_atomic_failure_preserve_exact_previous_bytes(self):
        self.input_file(); self.configure(); before=self.nod.options_path().read_bytes()
        expected=hashlib.sha256(before).hexdigest()
        changed=dict(self.value,url='https://new-nod.example.invalid',retired_sessions=['ses_synthetic_retired','ses_second_retired'])
        self.input_file(changed)
        with self.assertRaises(ValueError): self.configure()
        with self.assertRaises(ValueError): self.configure(False,'0'*64)
        with patch.object(self.nod.os,'replace',side_effect=OSError('fixture atomic failure')):
            with self.assertRaises(OSError): self.configure(False,expected)
        self.assertEqual(self.nod.options_path().read_bytes(),before)
        self.assertFalse(list(self.brief.glob('.nod-options-*')))
        self.configure(False,expected)
        self.assertEqual(self.nod.local_options(),changed)

    def test_strict_options_privacy_and_no_secret_fields(self):
        bad=[]
        for key,value in [('version',True),('retired_sessions',None),('retired_sessions',[{}]),('retired_sessions',['bad']),('url','http://user:password@example.invalid'),('image_base','http://not-https.invalid')]:
            v=copy.deepcopy(self.value); v[key]=value; bad.append(v)
        bad += [dict(self.value,token='not-accepted'),dict(self.value,retired_sessions=['ses_duplicate','ses_duplicate'])]
        missing=dict(self.value); missing.pop('retired_sessions'); bad.append(missing)
        for value in bad:
            with self.assertRaises(ValueError): self.nod.validate_options(value)
        self.input_file(); self.input.chmod(0o644)
        with self.assertRaises(ValueError): self.configure()
        self.assertFalse(self.nod.options_path().exists())
        self.input.chmod(0o600)
        linked=self.root/'linked.json'; linked.symlink_to(self.input)
        with self.assertRaises(OSError): self.nod.read_options(linked)


if __name__=='__main__': unittest.main()
