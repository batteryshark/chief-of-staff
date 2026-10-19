"""Fictional-only source tests; no native clients, model turns or live imports."""
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1]
MODULE = SOURCE / 'kits/chief/desk/filing'
sys.path.insert(0, str(MODULE))
import receiver as desk
import questions_policy as qp
import stage


class FilingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir(mode=0o700)
        self.project = self.root / 'study'
        self.project.mkdir()
        self.open = self.home / 'open.md'
        self.open.write_text('No current questions.')
        self.pointer = self.home / 'route.json'
        self.chief = {'session_id': 'fictional-chief-research', 'directory': str(self.home)}
        self.pointer.write_text(json.dumps(self.chief))
        self.c = {'version': 1, 'mode': 'LIVE', 'chief_home': str(self.home), 'chief_pointer': str(self.pointer), 'open_source': str(self.open), 'chief': self.chief, 'receiver_id': 'fictional-desk-research', 'projects': {str(self.project): {'title': 'Study', 'lead_session': 'fictional-study-lead', 'enabled': True}}}
        self.s = {'version': 1, 'admissions': {}, 'receipts': {}, 'projects': {}, 'digests': {}, 'pending': None, 'queue': []}
        self.r = {'kind': 'status', 'report_id': 'fictional-001', 'project': str(self.project), 'lead_session': 'fictional-study-lead', 'observed': '2026-10-01T09:00:00Z', 'landed': 'Source inventory recorded.', 'next': 'Compare methods.', 'your_part': None, 'questions': []}
        self.notes = []
        self.serial = 0

    def runop(self, op, **kwargs):
        return desk.operate(self.c, self.s, {'op': op, **kwargs})

    def prepare(self, **changes):
        return self.runop('prepare', report={**self.r, **changes}, source_native_id='fictional-input')

    def raw(self, notes=None, directory=None):
        return {'ok': True, 'action': 'knowledge.list', 'data': {'projectId': desk.scope(directory or str(self.project)), 'notes': self.notes if notes is None else notes}}

    def admit(self, **kwargs):
        return self.runop('admit', action_hash=desk.projection(self.s)['action_hash'], native_readback=self.raw(), **kwargs)

    def saved(self):
        a = self.s['pending']['actions'][0]
        self.serial += 1
        note = {'id': a.get('id') or 'fictional-note-' + str(self.serial), 'body': a['body'], 'origin': {'sessionId': self.c['receiver_id']}}
        return {'directory': a['directory'], 'native_result': {'ok': True, 'action': 'knowledge.save', 'data': {'projectId': desk.scope(a['directory']), 'note': note}}, 'actual_body_sha256': desk.body_hash(a['body'])}

    def ack(self, result):
        return self.runop('ack', action_hash=desk.projection(self.s)['action_hash'], native_outcome='confirmed_success', result=result)

    def step(self):
        self.assertTrue(self.admit()['execute_once'])
        result = self.saved()
        note = result['native_result']['data']['note']
        self.notes = [n for n in self.notes if n['id'] != note['id']] + [note]
        return self.ack(result)

    def file(self):
        while self.s['pending']:
            self.step()

    def test_digest_bounded_normalized_full_history_retained(self):
        for i in range(18):
            self.prepare(report_id='fictional-' + str(i), landed='😀' * 300 + ' milestone ' + str(i) + ' \t\n', observed=f'2026-10-01T09:{i:02}:00Z')
            self.file()
        self.assertEqual(len(self.s['admissions']), 18)
        self.assertEqual(len(self.s['receipts']), 18)
        body = self.s['digests'][str(self.project)]['body']
        self.assertLessEqual(desk.units(body), 3000)
        self.assertEqual(body, body.strip(desk.WHITESPACE))
        self.assertIn('fictional-17', body)
        self.assertNotIn('fictional-0 |', body)
        self.assertIn('milestone 0', self.s['admissions']['fictional-0']['report']['landed'])
        self.assertIn('milestone 0', self.s['receipts']['fictional-0']['digest_line'])
        projection = self.runop('inspect')
        self.assertLess(len(json.dumps(projection)), 220)
        self.assertNotIn('receipts', projection)

    def test_boundary_utf16_and_native_trim(self):
        self.assertEqual(desk.units('😀'), 2)
        line = 'x' * (3000 - desk.units(desk.HEADER + '\n\n'))
        self.assertEqual(desk.units(desk.recent_digest([line])), 3000)
        with self.assertRaises(ValueError):
            desk.recent_digest([line + 'x'])
        self.prepare(landed='done\ufeff', next='next \t')
        self.file()
        self.assertEqual(self.notes[-1]['body'], self.notes[-1]['body'].strip(desk.WHITESPACE))

    def test_pending_new_arrivals_finish_earlier_then_drain(self):
        first = self.prepare()
        for i in (2, 3):
            later = self.prepare(report_id=f'fictional-00{i}')
            self.assertEqual(first['report_id'], later['report_id'])
        self.assertEqual(len(self.s['queue']), 2)
        self.file()
        for i in (2, 3):
            self.assertEqual(self.runop('drain')['report_id'], f'fictional-00{i}')
            self.file()
        self.assertEqual(self.runop('drain')['action'], 'done')
        self.assertEqual(list(self.s['receipts']), ['fictional-001', 'fictional-002', 'fictional-003'])

    def test_durable_admission_before_execute_and_no_duplicate_queue(self):
        snapshots = []
        desk.operate(self.c, self.s, {'op': 'prepare', 'report': self.r}, lambda s: snapshots.append(copy.deepcopy(s)))
        self.assertIn('fictional-001', snapshots[0]['admissions'])
        self.assertEqual(len(snapshots[0]['queue']), 1)
        self.prepare()
        self.assertEqual(len(self.s['queue']), 0)
        out = desk.operate(self.c, self.s, {'op': 'admit', 'action_hash': desk.projection(self.s)['action_hash'], 'native_readback': self.raw()}, lambda s: snapshots.append(copy.deepcopy(s)))
        self.assertTrue(out['execute_once'])
        self.assertIn('admission', snapshots[-1]['pending'])

    def test_duplicate_changed_id_and_stale(self):
        self.prepare()
        self.file()
        before = copy.deepcopy(self.s)
        self.assertEqual(self.prepare()['action'], 'duplicate')
        self.assertEqual(self.s, before)
        with self.assertRaises(ValueError):
            self.prepare(landed='changed')
        self.prepare(report_id='fictional-older', observed='2026-09-01T09:00:00Z')
        self.assertEqual(desk.projection(self.s)['queued_action_types'], ['digest'])
        self.file()
        self.assertEqual(self.s['projects'], before['projects'])

    def test_hidden_forward_visible_and_your_part_never_forwards(self):
        self.prepare(questions=['Should sampling be monthly?'])
        self.assertEqual(desk.projection(self.s)['queued_action_types'], ['status', 'digest', 'forward'])
        self.assertTrue(desk.projection(self.s)['forward_planned'])
        self.s = {'version': 1, 'admissions': {}, 'receipts': {}, 'projects': {}, 'digests': {}, 'pending': None, 'queue': []}
        self.prepare(your_part='Your verdict after using it.', next='Historical approval recorded.')
        self.assertFalse(desk.projection(self.s)['forward_planned'])
        self.file()

    def test_actual_ack_rejects_id_only_short_body_wrong_hash_scope_kind_id(self):
        self.prepare()
        self.admit()
        good = self.saved()
        bads = [ {'note_id': 'fictional-only'} ]
        for transform in ('short', 'hash', 'scope', 'kind', 'missingid'):
            bad = copy.deepcopy(good)
            if transform == 'short':
                bad['native_result']['data']['note']['body'] = 'short'
            if transform == 'hash':
                bad['actual_body_sha256'] = '0' * 64
            if transform == 'scope':
                bad['native_result']['data']['projectId'] = 'wrong'
            if transform == 'kind':
                bad['native_result']['action'] = 'knowledge.list'
            if transform == 'missingid':
                bad['native_result']['data']['note']['id'] = ''
            bads.append(bad)
        for bad in bads:
            before = copy.deepcopy(self.s)
            with self.subTest(bad=bad), self.assertRaises((ValueError, KeyError)):
                self.ack(bad)
            self.assertEqual(self.s, before)
        self.ack(good)
        with self.assertRaises(ValueError):
            self.runop('ack', action_hash='stale', native_outcome='confirmed_success', result=good)

    def test_unknown_admitted_write_stops_then_exact_first_create_readback(self):
        self.prepare()
        self.admit()
        with self.assertRaises(ValueError):
            self.admit()
        note = self.saved()['native_result']['data']['note']
        self.notes = [note]
        out = self.admit()
        self.assertNotIn('execute_once', out)
        self.assertEqual(out['action']['type'], 'digest')
        self.assertTrue(self.s['pending']['completed'][0]['result']['reconciled_existing'])

    def test_unknown_first_create_foreign_and_ambiguous_stop(self):
        for mode in ('unadmitted', 'foreign', 'ambiguous', 'wrongkind'):
            with self.subTest(mode=mode):
                self.setUp()
                self.prepare()
                if mode != 'unadmitted':
                    self.admit()
                note = self.saved()['native_result']['data']['note']
                if mode == 'foreign':
                    note['origin']['sessionId'] = 'fictional-stranger'
                if mode == 'wrongkind':
                    note['body'] = desk.HEADER + '\nfictional-001'
                self.notes = [note]
                if mode == 'ambiguous':
                    self.notes.append({**note, 'id': 'fictional-second'})
                with self.assertRaises(ValueError):
                    self.admit()

    def test_cross_kind_marker_allows_status_then_digest_unrelated_untouched(self):
        unrelated = {'id': 'fictional-other-owner', 'body': 'A lead-owned Note.', 'origin': {'sessionId': 'fictional-stranger'}}
        self.notes = [unrelated]
        self.prepare()
        self.step()
        self.assertEqual(self.s['pending']['actions'][0]['type'], 'digest')
        self.step()
        self.assertIn(unrelated, self.notes)
        self.assertEqual(len(self.notes), 3)

    def test_known_saved_before_ack_no_rewrite_and_cas_external_edit_stops(self):
        self.prepare()
        self.file()
        self.prepare(report_id='fictional-002', observed='2026-10-01T10:00:00Z')
        self.admit()
        saved = self.saved()['native_result']['data']['note']
        self.notes = [n if n['id'] != saved['id'] else saved for n in self.notes]
        self.assertNotIn('execute_once', self.admit())
        self.step()
        self.prepare(report_id='fictional-003', observed='2026-10-01T11:00:00Z')
        self.notes[0]['body'] = 'human edited'
        with self.assertRaises(ValueError):
            self.admit()

    def test_payload_cannot_select_recipient_and_two_distinct_domains(self):
        for domain in ('life', 'research'):
            with self.subTest(domain=domain):
                self.setUp()
                self.c['chief'] = {'session_id': 'fictional-' + domain + '-chief', 'directory': str(self.home)}
                self.c['receiver_id'] = 'fictional-' + domain + '-desk'
                self.c['projects'][str(self.project)]['title'] = domain.title()
                self.c['projects'][str(self.project)]['lead_session'] = 'fictional-' + domain + '-lead'
                self.r['lead_session'] = 'fictional-' + domain + '-lead'
                self.prepare(questions=['A real explicit question?'])
                self.assertEqual(self.s['pending']['actions'][-1]['target'], self.c['chief'])
                with self.assertRaises(ValueError):
                    self.prepare(report_id='fictional-injection', target={'session_id': 'attacker'})
                self.step()
                self.step()
                self.assertTrue(all(n['origin']['sessionId'] == self.c['receiver_id'] for n in self.notes))

    def test_oversize_original_remains_durably_queued_without_action(self):
        with self.assertRaises(ValueError):
            self.prepare(landed='😀' * 1501)
        self.assertEqual(self.s['admissions']['fictional-001']['report']['landed'], '😀' * 1501)
        self.assertEqual(len(self.s['queue']), 1)
        self.assertIsNone(self.s['pending'])

    def test_wrong_owned_id_ack_and_wrong_readback_scope(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.runop('admit', action_hash=desk.projection(self.s)['action_hash'], native_readback=self.raw(directory='/fictional/other'))
        self.file()
        self.prepare(report_id='fictional-new', observed='2026-10-01T10:00:00Z')
        self.admit()
        bad = self.saved()
        bad['native_result']['data']['note']['id'] = 'fictional-wrong'
        with self.assertRaises(ValueError):
            self.ack(bad)

    def test_exact_trusted_handover_only(self):
        body = 'Existing lead-owned status transferred explicitly.'
        self.c['projects'][str(self.project)]['handover'] = {'note_id': 'fictional-transfer', 'body': body, 'body_hash': desk.body_hash(body), 'authorization': 'Fictional operator transfer'}
        stage.validate_config(self.c)
        self.notes = [{'id': 'fictional-transfer', 'body': body}]
        self.prepare()
        self.assertEqual(self.s['pending']['actions'][0]['expected'], body)
        self.step()
        self.assertEqual(self.s['projects'][str(self.project)]['note_id'], 'fictional-transfer')

    def test_mixed_known_new_questions_pending_not_dropped_or_duplicated(self):
        r = {**self.r, 'questions': ['Known question?', 'New question?']}
        text = 'Known question?'
        result = qp.review(r, {}, str(self.open), str(self.open), text, desk.body_hash(text), 'new_unasked')
        self.assertEqual(result['state'], 'pending')

    def test_actual_source_snapshot_and_changed_pointer_checked_in_staged_cli(self):
        c = copy.deepcopy(self.c)
        c['mode'] = 'DISABLED'
        c['projects'][str(self.project)]['enabled'] = False
        dest = self.home / 'runtime'
        stage.stage(self.home, dest, c)
        c = copy.deepcopy(self.c)
        c['projects'][str(self.project)]['enabled'] = True
        (dest / 'control.json').write_text(json.dumps(c))
        self.question()
        self.review()
        (dest / 'state.json').write_text(json.dumps(self.s))
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.home), 'TMPDIR': str(self.root), 'XDG_CONFIG_HOME': str(self.root / 'config'), 'XDG_STATE_HOME': str(self.root / 'state'), 'PYTHONDONTWRITEBYTECODE': '1'}
        def call(req):
            return subprocess.run([sys.executable, str(dest / 'receiver.py')], input=json.dumps(req), text=True, capture_output=True, env=env, timeout=10)
        before = (dest / 'state.json').read_bytes()
        out = call({'op': 'question_source', 'source': str(self.open)})
        self.assertEqual(out.returncode, 0, out.stderr)
        actual = json.loads(out.stdout)
        self.assertEqual(actual['body'], self.open.read_text())
        self.assertFalse(actual['eligible'])
        self.assertEqual((dest / 'state.json').read_bytes(), before)
        self.assertNotEqual(call({'op': 'question_source', 'source': '/fictional/wrong'}).returncode, 0)
        req = {'op': 'admit', 'action_hash': desk.projection(self.s)['action_hash'], 'source': str(self.open), 'source_sha256': actual['source_sha256'], 'current_chief': self.chief}
        self.pointer.write_text(json.dumps({'session_id': 'fictional-new-chief', 'directory': str(self.home)}))
        self.assertNotEqual(call(req).returncode, 0)
        self.pointer.write_text(json.dumps(self.chief))
        self.open.write_text('New actual open items.')
        self.assertNotEqual(call(req).returncode, 0)
        self.assertEqual((dest / 'state.json').read_bytes(), before)

    def test_strict_input_disabled_unknown_registration_and_oversize_retained(self):
        for delta in ({'kind': 'answer'}, {'questions': 'question'}, {'observed': '2099-01-01T00:00:00Z'}, {'your_part': True}, {'report_id': 'bad\nID'}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                self.prepare(**delta)
        self.c['mode'] = 'DISABLED'
        self.prepare()
        self.assertIsNone(self.s['pending'])
        with self.assertRaises(ValueError):
            self.runop('drain')
        self.c['mode'] = 'LIVE'
        self.c['projects'] = {}
        with self.assertRaises(ValueError):
            self.runop('drain')
        self.assertIn('fictional-001', self.s['admissions'])
        self.assertEqual(len(self.s['queue']), 1)
        with self.assertRaises(ValueError):
            desk.loads('{"op":"inspect","op":"admit"}')

    def question(self):
        self.prepare(questions=['Should the sampling be monthly?'])
        self.step()
        self.step()
        return desk.projection(self.s)['action_hash']

    def review(self, classification='new_unasked', **kwargs):
        text = self.open.read_text()
        return self.runop('question_review', action_hash=desk.projection(self.s)['action_hash'], **{'source': str(self.open), 'open_text': text, 'source_sha256': desk.body_hash(text), 'classification': classification, **kwargs})

    def test_new_question_requires_review_current_source_and_route(self):
        h = self.question()
        with self.assertRaises(ValueError):
            self.runop('admit', action_hash=h)
        self.assertEqual(self.review()['question_review']['state'], 'eligible')
        for wrong in ({'current_chief': {'session_id': 'fictional-wrong'}}, {'open_text': 'changed'}):
            params = {'action_hash': h, 'source': str(self.open), 'open_text': self.open.read_text(), 'current_chief': self.chief, **wrong}
            with self.assertRaises(ValueError):
                self.runop('admit', **params)
        out = self.runop('admit', action_hash=h, source=str(self.open), open_text=self.open.read_text(), current_chief=self.chief)
        self.assertTrue(out['execute_once'])
        with self.assertRaises(ValueError):
            self.runop('admit', action_hash=h)
        with self.assertRaises(ValueError):
            self.ack({'dispatched': True, 'session_id': 'wrong', 'dispatch_result': {'id': 'fictional-dispatch'}})
        self.ack({'dispatched': True, 'session_id': self.chief['session_id'], 'dispatch_result': {'id': 'fictional-dispatch'}})
        self.assertIsNone(self.s['pending'])

    def test_questions_unknown_wrong_source_open_priorasked_receipts(self):
        for case in ('unknown', 'wrongsource', 'badsha', 'open', 'reworded', 'priorasked', 'ownreceipt'):
            with self.subTest(case=case):
                self.setUp()
                if case == 'priorasked':
                    self.r['your_part'] = 'Already asked the chief about this.'
                self.question()
                if case == 'open':
                    self.open.write_text('Should the sampling be monthly?')
                if case == 'ownreceipt':
                    self.s['receipts']['fictional-old'] = {'report': {**self.r, 'questions': ['Should the sampling be monthly?']}, 'completed': [{'action': {'type': 'forward'}, 'result': {'dispatched': True}}]}
                args = {'classification': 'new_unasked'}
                if case == 'unknown': args['classification'] = 'unknown'
                if case == 'wrongsource': args['source'] = '/fictional/wrong'
                if case == 'badsha': args['source_sha256'] = '0' * 64
                if case == 'reworded': args['classification'] = 'already_open'
                out = self.review(**args)
                expected = 'deduplicated' if case == 'ownreceipt' else 'eligible' if case == 'priorasked' else 'pending'
                self.assertEqual(out['question_review']['state'], expected)

    def test_review_evidence_caller_retains_exact_observation(self):
        self.question()
        text = str(self.project) + ' | fictional-study-lead | Monthly sampling decision is open.'
        self.open.write_text(text)
        evidence = [{'question': 'Should the sampling be monthly?', 'project': str(self.project),
                     'lead_session': 'fictional-study-lead', 'basis': 'current_chief_open',
                     'excerpt': text, 'source_sha256': desk.body_hash(text)}]
        out = self.review('already_open', evidence=evidence)
        self.assertEqual(out['question_review']['state'], 'deduplicated')
        retained = self.s['receipts']['fictional-001']
        self.assertEqual(retained['question_review']['evidence'], evidence)
        self.assertEqual(retained['question_review']['source'], str(self.open))
        self.assertEqual(len(retained['suppressed_actions']), 1)
        self.assertFalse(any(i['action']['type'] == 'forward' for i in retained['completed']))


class StageTests(FilingTests):
    # Only staging-specific methods are collected below, not inherited tests.
    def disabled(self):
        c = copy.deepcopy(self.c)
        c['mode'] = 'DISABLED'
        c['projects'][str(self.project)]['enabled'] = False
        return c

    def test_stage_absent_only_seven_files_private_inert_cli(self):
        dest = self.home / 'desk'
        old_umask = os.umask(0o777)
        try:
            stage.stage(self.home, dest, self.disabled())
        finally:
            os.umask(old_umask)
        self.assertEqual(len(list(dest.iterdir())), 7)
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in dest.iterdir()))
        with self.assertRaises(ValueError):
            stage.stage(self.home, dest, self.disabled())
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.home), 'TMPDIR': str(self.root), 'XDG_CONFIG_HOME': str(self.root / 'config'), 'XDG_STATE_HOME': str(self.root / 'state'), 'PYTHONDONTWRITEBYTECODE': '1'}
        out = subprocess.run([sys.executable, str(dest / 'receiver.py')], input='{"op":"inspect"}', text=True, capture_output=True, env=env, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)['action'], 'done')
        out = subprocess.run([sys.executable, str(dest / 'receiver.py')], input='{"op":"drain"}', text=True, capture_output=True, env=env, timeout=10)
        self.assertNotEqual(out.returncode, 0)

    def test_stage_preflight_all_before_writes(self):
        for problem in ('enabled', 'mode', 'link', 'unsafehome', 'outside', 'schema', 'noncanonical'):
            with self.subTest(problem=problem):
                self.setUp()
                c = self.disabled()
                dest = self.home / 'desk'
                if problem == 'enabled': c['projects'][str(self.project)]['enabled'] = True
                if problem == 'mode': c['mode'] = 'LIVE'
                if problem == 'schema': c['repair'] = {}
                if problem == 'link': dest.symlink_to(self.project)
                if problem == 'unsafehome': self.home.chmod(0o777)
                if problem == 'outside': dest = self.root / 'outside'
                if problem == 'noncanonical': c['chief_home'] = str(self.home) + '/..'
                with self.assertRaises(ValueError):
                    stage.stage(self.home, dest, c)
                self.assertFalse(dest.is_dir() and not dest.is_symlink())

    def test_runtime_hardlink_mode_uid_and_link_refuse(self):
        dest = self.home / 'desk'
        stage.stage(self.home, dest, self.disabled())
        file = dest / 'state.json'
        desk.metadata(file)
        file.chmod(0o644)
        with self.assertRaises(ValueError): desk.metadata(file)
        file.chmod(0o600)
        os.link(file, dest / 'second')
        with self.assertRaises(ValueError): desk.metadata(file)
        (dest / 'second').unlink()
        (dest / 'linked').symlink_to(file)
        with self.assertRaises(ValueError): desk.metadata(dest / 'linked')
        fake = SimpleNamespace(st_uid=os.getuid() + 1, st_mode=stat.S_IFREG | 0o600, st_nlink=1)
        with patch.object(Path, 'lstat', return_value=fake), self.assertRaises(ValueError):
            desk.metadata(file)

    def test_source_hardlink_blocks_staging_before_any_target(self):
        original = Path.lstat
        def metadata(p):
            s = original(p)
            if p == MODULE / 'instructions.md':
                return SimpleNamespace(st_uid=os.getuid(), st_mode=s.st_mode, st_nlink=2)
            return s
        with patch.object(Path, 'lstat', metadata), self.assertRaises(ValueError):
            stage.stage(self.home, self.home / 'desk', self.disabled())
        self.assertFalse((self.home / 'desk').exists())


# Avoid duplicate inherited collection while sharing helpers and setup.
for _name in list(FilingTests.__dict__):
    if _name.startswith('test_'):
        setattr(StageTests, _name, None)


if __name__ == '__main__':
    unittest.main()
