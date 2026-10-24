"""Current decision contract, actual rendered helper, offline transport spies only."""
import argparse
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC / 'scripts'))
import render


def valid_card():
    return {'title':'Ship the fix?', 'summary':'Tests pass.', 'recommended':'yes', 'default':'No change.',
            'options':[{'id':'yes','label':'Ship','kind':'approve','description':'Ship today.'},
                       {'id':'no','label':'Wait','kind':'reject','description':'Keep this version.'}]}


class ChiefNodTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        script = self.root / 'chief_nod.py'
        script.write_text(render.render('scripts/chief-nod', str(self.root)))
        spec = importlib.util.spec_from_file_location('nod_contract', script)
        self.nod = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.nod)
        (self.root/'chief.json').write_text(json.dumps({'session':'ses_chief','directory':str(self.root)}))
        options=self.root/'nod-options.json'
        options.write_text(json.dumps({'version':1,'url':'http://127.0.0.1:8767',
            'image_base':'https://images.example/chief-images','retired_sessions':[self.nod.QUIET_CHIEF]}))
        options.chmod(0o600)
        self.env = patch.dict(os.environ, {'OPENCODE_SESSION_ID':'ses_chief','CHIEF_NOD_STATE_DIR':str(self.root/'state'),
                                          'CHIEF_NOD_RETIRED_SESSION':self.nod.QUIET_CHIEF})
        self.env.start()
        self.bus_probe = patch.object(self.nod.socket, 'create_connection', side_effect=OSError('fixture offline'))
        self.bus_probe.start()

    def tearDown(self):
        self.bus_probe.stop()
        self.env.stop(); self.tmp.cleanup()

    def args(self, **kw):
        return argparse.Namespace(**dict(dict(file=None,channel='chief',image=None,recommended=None,
            recommendation=None,dry_run=False,origin_session=None,origin_directory=None,reference=None,
            limits=None,answer_route='origin'), **kw))

    def invoke(self, card, args=None):
        with patch.object(self.nod.sys,'stdin',io.StringIO(json.dumps(card))), patch('builtins.print'):
            return self.nod.ask(args or self.args())

    def assert_refused_without_effect(self, card):
        before = copy.deepcopy(card)
        with patch.object(self.nod,'call') as api, patch.object(self.nod,'publish_image') as image, \
             patch.object(self.nod,'ask_binding') as binding, patch.object(self.nod,'state') as state:
            with self.assertRaises((ValueError, SystemExit)):
                self.invoke(dict(card,image_file='/not-published.png'))
            for spy in (api,image,binding,state): spy.assert_not_called()
        self.assertEqual(card,before)

    def test_rendered_boundaries_599_600_601_and_raw_limit(self):
        base=valid_card(); base['summary']='S'
        rendered=self.nod.decision_card(base)
        size=len(rendered['body_markdown'])+len(rendered['summary'])
        # Body adds one newline when nonempty. Boundary includes generated copy.
        for n in (599,600,601):
            card=dict(base,body_markdown='x'*(n-size-1))
            if n<=600:
                result=self.nod.decision_card(card)
                self.assertEqual(len(result['summary'])+len(result['body_markdown']),n)
            else: self.assert_refused_without_effect(card)
        self.assert_refused_without_effect(dict(base,summary='x'*601))
        # Nod would derive this long first body line as its summary.
        self.assert_refused_without_effect(dict(base,summary='',body_markdown='x'*300))

    def test_question_count_and_options_counts(self):
        for title in ('Ship the fix','Ship? Wait?'):
            self.assert_refused_without_effect(dict(valid_card(),title=title))
        self.assert_refused_without_effect(dict(valid_card(),summary='Why now?'))
        for n in (0,1,4):
            card=valid_card(); card['options']=[dict(card['options'][0],id=f'o{i}') for i in range(n)]
            self.assert_refused_without_effect(card)
        card=valid_card();card['options'].append({'id':'later','label':'Tomorrow','description':'Ship tomorrow.'})
        result=self.nod.decision_card(card);self.assertEqual(len(result['options']),3)

    def test_outcomes_markers_and_forbidden_choices(self):
        for field in ('recommended','default'):
            card=valid_card();del card[field];self.assert_refused_without_effect(card)
        for outcome in ('', 'First\nSecond','First\rSecond','First\u2028Second','First\n'):
            card=valid_card();card['options'][0]['description']=outcome;self.assert_refused_without_effect(card)
        for text in ('Review','Discuss','READ-THIS','Review / discuss'):
            card=valid_card();card['options'][0]['label']=text;self.assert_refused_without_effect(card)
        card=valid_card();card['options'][1]['label']='Wait (Recommended)';self.assert_refused_without_effect(card)
        for extra in ({'approval':{'approve':'Yes'}},{'notes':True},{'tradeoff':True},{'template_id':'x'}):
            self.assert_refused_without_effect(dict(valid_card(),**extra))

    def test_valid_card_exact_choices_and_single_tracked_post(self):
        card=valid_card();before=copy.deepcopy(card)
        with patch.object(self.nod,'native_origin',return_value={'session':'ses_chief','directory':str(self.root)}), \
             patch.object(self.nod,'call',return_value={'request_id':'r1'}) as api, patch.object(self.nod,'reconcile'):
            self.assertEqual(self.invoke(card),0)
        api.assert_called_once();method,url,payload=api.call_args.args
        self.assertEqual((method,url),('POST','/api/v1/requests'))
        self.assertEqual([o['id'] for o in payload['options']],['yes','no'])
        self.assertEqual(payload['options'][0]['label'],'Ship (Recommended)')
        self.assertIn('Default if no answer: No change.',payload['body_markdown'])
        self.assertNotIn('description',payload['options'][0]);self.assertEqual(card,before)
        self.assertEqual(json.loads((self.root/'state/state.json').read_text())['requests']['r1']['origin']['session'],'ses_chief')

    def test_lead_bus_spoof_and_stale_pointer_refuse_before_binding_or_image(self):
        for env,args in [('ses_lead',self.args()),('ses_lead',self.args(origin_session='ses_chief')),
                         ('ses_chief',self.args(answer_route='heartbeat-bus'))]:
            with patch.dict(os.environ,{'OPENCODE_SESSION_ID':env}),patch.object(self.nod,'call') as api, \
                 patch.object(self.nod,'ask_binding') as binding,patch.object(self.nod,'publish_image') as image:
                with self.assertRaises(ValueError): self.invoke(dict(valid_card(),image_file='/fake.png'),args)
                for spy in (api,binding,image):spy.assert_not_called()
        (self.root/'chief.json').write_text(json.dumps({'session':'ses_new','directory':str(self.root)}))
        self.assert_refused_without_effect(valid_card())

    def test_dry_run_needs_no_token_or_native_origin_and_alert_is_explicit(self):
        with patch.object(self.nod,'call') as api,patch.object(self.nod,'native_origin') as native:
            self.assertEqual(self.invoke(valid_card(),self.args(dry_run=True)),0)
            api.assert_not_called();native.assert_not_called()
        self.assert_refused_without_effect({'title':'Informational message','summary':'Done.'})

    def test_unknown_fields_and_callback_refusal(self):
        self.assert_refused_without_effect(dict(valid_card(),source_id='unsupported'))
        with patch.object(self.nod,'native_origin',return_value={'session':'ses_chief','directory':str(self.root)}), \
             patch.object(self.nod,'call') as api,patch.object(self.nod,'publish_image') as image:
            with self.assertRaises(ValueError): self.invoke(dict(valid_card(),callback_url='https://invalid.example',image_file='/fake'))
            api.assert_not_called();image.assert_not_called()
            self.assertFalse((self.root/'state').exists())

    def test_image_validation_and_read_only_decision_path(self):
        png=self.root/'pic.png';png.write_bytes(b'\x89PNG\r\n\x1a\n'+b'0'*20)
        with patch.dict(os.environ,{'CHIEF_NOD_IMAGE_DIR':str(self.root/'images'),'CHIEF_NOD_IMAGE_BASE':'https://images.example/chief-images'}):
            self.nod.publish_image(str(png),False);self.assertFalse((self.root/'images').exists())
            url=self.nod.publish_image(str(png),True)
            self.assertEqual((self.root/'images'/url.rsplit('/',1)[1]).read_bytes(),png.read_bytes())
        with patch.object(self.nod,'call',return_value={'request_id':'r1','status':'pending'}) as api,patch('builtins.print'):
            self.nod.decision_json(argparse.Namespace(request_id='r1'))
            api.assert_called_once_with('GET','/api/v1/requests/r1/decision')
        self.assertFalse((self.root/'state').exists())


class ImageServerTest(unittest.TestCase):
    def test_serves_only_published_images_read_only(self):
        import socket
        import subprocess
        import time
        import urllib.error
        import urllib.request
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'images'
            folder.mkdir()
            png = b'\x89PNG\r\n\x1a\n' + b'1' * 8
            (folder / 'abcdEFGH_1-xyz.png').write_bytes(png)
            (folder / 'secret.txt').write_text('no')
            (Path(tmp) / 'outside.png').write_bytes(png)
            (folder / 'linkedAAAA.png').symlink_to(Path(tmp) / 'outside.png')
            script = Path(tmp) / 'srv'
            script.write_text(render.render('scripts/chief-images-server', '/fixture/chief'))
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0))
                port = s.getsockname()[1]
            proc = subprocess.Popen([sys.executable, '-I', str(script), '--port', str(port), '--dir', str(folder)])
            try:
                base = f'http://127.0.0.1:{port}'
                for _ in range(50):
                    try:
                        urllib.request.urlopen(base + '/health', timeout=1)
                        break
                    except OSError:
                        time.sleep(0.1)
                got = urllib.request.urlopen(base + '/chief-images/abcdEFGH_1-xyz.png', timeout=5)
                self.assertEqual((got.status, got.headers['Content-Type'], got.read()), (200, 'image/png', png))
                for route in ('/chief-images/', '/chief-images/secret.txt', '/chief-images/linkedAAAA.png',
                              '/chief-images/..%2Foutside.png', '/chief-images/../outside.png', '/'):
                    with self.assertRaises(urllib.error.HTTPError, msg=route) as e:
                        urllib.request.urlopen(base + route, timeout=5)
                    self.assertEqual(e.exception.code, 404, route)
                post = urllib.request.Request(base + '/chief-images/abcdEFGH_1-xyz.png', data=b'x', method='POST')
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(post, timeout=5)
            finally:
                proc.terminate()
                proc.wait(timeout=5)


if __name__=='__main__': unittest.main()
