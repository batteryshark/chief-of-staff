import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runway.ledger import Ledger
from runway.cli import handle


class DispatchRecordTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get('HOST_DISPATCH_TEST_ROOT', str(Path(tempfile.gettempdir()) / 'opencode')))
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.path = Path(self.tmp.name) / 'ledger.sqlite3'
        self.ledger = Ledger(self.path)
        self.a = {'id':'a', 'job':'dummy', 'scope':self.tmp.name, 'state':'admitted',
                  'task':{'directory':self.tmp.name}, 'model':'openai/alias-fast',
                  'variant':'high', 'agent':'build', 'message_id':'msg_a', 'session_id':None}
        self.ledger.save(self.a)
        self.value = {'id':'a', 'inputID':'msg_a', 'state':'creating', 'agent':'build',
                      'model':{'providerID':'openai','id':'alias-fast','variant':'high'},
                      'directory':self.tmp.name, 'text':'dummy', 'textHash':hashlib.sha256(b'dummy').hexdigest(),
                      'origin':{'sessionID':'ses_origin','messageID':'msg_tool','callID':'call_a','directory':self.tmp.name}}

    def tearDown(self):
        self.ledger.close(); self.tmp.cleanup()

    def advance(self, state, expected):
        self.value = {**self.value, 'state':state}
        if state != 'creating': self.value['sessionID'] = 'ses_worker'
        return self.ledger.dispatch_save('a', self.value, expected, 1792733000)

    def test_locked_existing_body_cas_no_new_table_or_lifecycle(self):
        self.advance('creating', None)
        self.assertEqual(self.ledger.get('a')['state'], 'uncertain')
        other = Ledger(self.path)
        try:
            with self.assertRaisesRegex(ValueError, 'CAS conflict'):
                other.dispatch_save('a', self.value, None, 1792733000)
        finally: other.close()
        self.advance('created', 'creating'); self.advance('uncertain', 'created')
        self.advance('admitted', 'uncertain')
        a = self.ledger.get('a')
        self.assertEqual(a['state'], 'running'); self.assertEqual(a['session_id'], 'ses_worker')
        tables = {r[0] for r in self.ledger.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {'attempts', 'preferences', 'cooldowns'})

    def test_creation_uncertainty_retains_claim(self):
        self.advance('creating', None)
        a = self.ledger.get('a')
        self.assertEqual(a['state'], 'uncertain'); self.assertIsNone(a['session_id'])
        with self.assertRaises(ValueError): self.advance('creating', None)

    def test_reserved_selection_and_origin_cannot_change(self):
        for key, value in [('inputID','msg_other'), ('directory','/foreign'), ('agent','other')]:
            d = copy.deepcopy(self.value); d[key] = value
            with self.assertRaises(ValueError): self.ledger.dispatch_save('a', d, None, 1)
        self.advance('creating', None)
        d = copy.deepcopy(self.value); d.update(state='created',sessionID='ses_worker'); d['origin']['callID']='wrong'
        with self.assertRaisesRegex(ValueError, 'immutable'): self.ledger.dispatch_save('a', d, 'creating', 1)

    def test_reused_admission_refuses(self):
        self.a['session_id']='ses_old'; self.ledger.save(self.a)
        with self.assertRaisesRegex(ValueError,'fresh unbound'): self.advance('creating', None)

    def test_worker_ownership_conflict(self):
        self.ledger.save({**self.a,'id':'b','session_id':'ses_worker'})
        self.advance('creating', None)
        with self.assertRaisesRegex(ValueError,'another admission'): self.advance('created', 'creating')

    def test_incomplete_stays_collectable_not_resendable(self):
        self.advance('creating',None); self.advance('created','creating'); self.advance('uncertain','created'); self.advance('admitted','uncertain')
        a=self.ledger.dispatch_incomplete('a','msg_a')
        self.assertEqual(a['state'],'uncertain'); self.assertEqual(a['host_dispatch']['state'],'admitted')
        with self.assertRaises(ValueError): self.ledger.dispatch_incomplete('a','msg_wrong')
        with self.assertRaises(ValueError): self.ledger.bind('a',{'id':'ses_worker'},1)
        with self.assertRaises(ValueError): self.ledger.finish('a','completed',{}, {},1)
        self.value['result']={'origin':self.value['origin'],'attemptID':'a','sessionID':'ses_worker','inputID':'msg_a',
                              'model':self.value['model'],'assistantID':'msg_reply','idleID':'msg_idle','text':'dummy'}
        self.advance('collected','admitted')
        self.assertEqual(self.ledger.get('a')['host_dispatch']['result']['inputID'],'msg_a')

    def test_cli_internal_actions_use_same_ledger(self):
        result=handle({'action':'dispatch-save','attempt':'a','value':self.value,'expected_state':None}, {}, self.ledger, None, None)
        self.assertEqual(result['state'],'uncertain')
        self.assertEqual(handle({'action':'dispatch-get','attempt':'a'}, {}, self.ledger, None, None)['host_dispatch']['origin'],self.value['origin'])

    def test_foreign_result_refuses(self):
        self.advance('creating',None); self.advance('created','creating'); self.advance('uncertain','created'); self.advance('admitted','uncertain')
        self.value['result']={'origin':{**self.value['origin'],'callID':'wrong'}}
        with self.assertRaisesRegex(ValueError,'exact input/caller'): self.advance('collected','admitted')


if __name__ == '__main__': unittest.main()
