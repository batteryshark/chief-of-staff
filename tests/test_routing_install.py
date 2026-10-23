import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('routing_install', ROOT / 'scripts/install-routing.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class RoutingInstall(unittest.TestCase):
    def fixture(self, home):
        location = home / 'fixture'; location.mkdir()
        output = location / 'runtime'; output.mkdir()
        (output / 'package.json').write_text('{"name":"chief-runway-opencode"}')
        (output / 'index.js').write_text('// isolated build fixture')
        pointer = location / 'chief.json'; pointer.write_text(json.dumps({'session':'ses_fixture','directory':str(location)}))
        record = location / 'LEAD.md'; record.write_text('## Stop conditions\nOnly the approved fixture check.\n')
        manifest = {'location':str(location),'pluginRoot':str(output),'hostDispatch':{
            'chiefPointerFile':str(pointer),'holdBindings':{str(location):[{'file':str(record),
                'heading':'## Stop conditions','allowedQuote':'Only the approved fixture check.'}]},
            'workerAgent':'build','completionTimeoutMs':25000}}
        config = location / '.opencode/opencode.json'; config.parent.mkdir()
        config.write_text(json.dumps({'plugins':[{'package':output.as_uri(),'options':{'unrelated':True}}],
                                     'agents':{'other':{'description':'preserved'}}}))
        return location, config, manifest

    def test_scoped_native_options_preserve_unrelated_and_touch_no_global_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve(); location,config,manifest=self.fixture(home)
            with patch.object(Path,'home',return_value=home):
                before=config.read_bytes(); installer.install(ROOT,'dry',manifest); self.assertEqual(config.read_bytes(),before)
                installer.install(ROOT,'install',manifest); result=json.loads(config.read_text())
                self.assertTrue(result['plugins'][0]['options']['unrelated'])
                self.assertEqual(result['plugins'][0]['options']['hostDispatch'],manifest['hostDispatch'])
                self.assertEqual(result['agents']['other']['description'],'preserved')
                self.assertEqual({r['resource'] for r in result['policies']},
                                 {'plugin:'+str(ROOT/'dist'),'plugin:'+str(ROOT/'dist/index.js')})
                saved=config.read_bytes();installer.install(ROOT,'install',manifest);self.assertEqual(config.read_bytes(),saved)
            self.assertFalse((home/'.config/opencode').exists())
            self.assertFalse((home/'.local/bin/chief-runway').exists())
            self.assertFalse((home/'.chief-of-staff/runway').exists())

    def test_missing_changed_fixture_or_credential_options_refuse_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve();location,config,manifest=self.fixture(home);before=config.read_bytes()
            variants=[]
            for mutate in (lambda v:v.pop('holdBindings'),lambda v:v.update(fixtureMode=True),
                           lambda v:v.update(token='forbidden'),lambda v:v.update(completionTimeoutMs=True),
                           lambda v:v.update(completionTimeoutMs=60001),lambda v:v.pop('chiefPointerFile')):
                value=json.loads(json.dumps(manifest));mutate(value['hostDispatch']);variants.append(value)
            value=json.loads(json.dumps(manifest));value['hostDispatch']['holdBindings'][str(location)][0]['allowedQuote']='Manufactured clear.';variants.append(value)
            with patch.object(Path,'home',return_value=home):
                for value in variants:
                    with self.assertRaises((ValueError,KeyError)):installer.install(ROOT,'install',value)
                    self.assertEqual(config.read_bytes(),before)
                config.with_suffix('.jsonc').write_text('{}')
                with self.assertRaisesRegex(ValueError,'JSONC'):installer.install(ROOT,'install',manifest)


if __name__ == '__main__': unittest.main()
