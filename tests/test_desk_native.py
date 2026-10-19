"""Offline private-host fixtures. No native API, model, managed tool or service."""
import json
import shutil
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import test_desk as fixture
from desk_native import NativeStore
from desk_store import fingerprint
from hygiene_fixtures import outputs, pinned_print
import test_modular as modular


class NativeTests(unittest.TestCase):
    setUp = fixture.DeskTests.setUp

    def test_fixture_exact_ack_rule_rechecks_report_hash_recipient_epoch_expiry(self):
        s = self.native()
        report = dict(project='lead-a', id='first-smoke', source_revision=1,
            observed=datetime.now(timezone.utc).isoformat(), landed='Owned fixture report filed.',
            next='Stop after first smoke.', your_part=None, state='active', request='ack', rule='fixture-first-smoke')
        rule = dict(id='fixture-first-smoke', project='lead-a', action='ack', active=True,
            fixture_only=True, report_hash=fingerprint(report), recipient='ses_lead', epoch=1,
            answer='Filed. No approval implied.', evidence='trusted-operator-exact-benign-fixture',
            expires=(datetime.now(timezone.utc) + timedelta(seconds=110)).isoformat())
        s.registry['projects']['lead-a'] = s.registry['projects']['fixture']
        (self.home / 'desk/routes.json').write_text(json.dumps({'version': 1, 'projects': {
            'lead-a': {'enabled': True, 'epoch': 1, 'leads': ['ses_lead']}}}))
        s.registry['rules'] = {rule['id']: rule}
        self.assertEqual(s.classify(report, True)[0], 'ack')
        for key, bad in [('recipient', 'ses_foreign'), ('epoch', 2), ('action', 'technical-delegation'),
                         ('expires', '2000-01-01T00:00:00Z'), ('answer', 'Approved'),
                         ('report_hash', 'a' * 64), ('active', False), ('extra', 'untrusted')]:
            with self.subTest(key=key):
                s.registry['rules'][rule['id']] = {**rule, key: bad}
                self.assertEqual(s.classify(report, True)[0], 'escalate')
        s.registry['rules'][rule['id']] = rule
        self.assertEqual(s.classify({**report, 'landed': 'mutated'}, True)[0], 'escalate')
        self.assertEqual(s.classify(report, False)[0], 'quarantine')

    def native(self):
        s = NativeStore(self.home)
        self.addCleanup(s.close)
        self.cfg = {'version': 1, 'enabled': True, 'desk_agent': 'native-desk',
                    'chief_agent': 'native-chief', 'home_projectId': 'path_home', 'home_nativeProjectID': 'core_home',
                    'overview_create': True, 'projects': {'fixture': {
                        'enabled': True, 'lead_agent': 'native-lead',
                        'projectId': 'path_project', 'nativeProjectID': 'core_project', 'note_create': True}}}
        self.save_cfg()
        for name in ('desk', 'chief'):
            (self.home / (name + '.json')).write_text(json.dumps({
                'session': 'ses_' + name, 'directory': str(self.home), 'updated': '2026-10-01T00:00:00Z'}))
        (self.home / 'desk/routes.json').write_text(json.dumps({'version': 1, 'projects': {
            'fixture': {'enabled': True, 'epoch': 1, 'leads': ['ses_lead']}}}))
        self.lead = {'id': 'ses_lead', 'agent': 'native-lead', 'projectID': 'core_project', 'location': {'directory': str(self.project)}, 'time': {}}
        self.desk = {'id': 'ses_desk', 'agent': 'native-desk', 'projectID': 'core_home', 'location': {'directory': str(self.home)}, 'time': {}}
        self.chief = {'id': 'ses_chief', 'agent': 'native-chief', 'projectID': 'core_home', 'location': {'directory': str(self.home)}, 'time': {}}
        self.call = {'sessionID': 'ses_lead', 'agent': 'native-lead', 'messageID': 'msg_assistanttool', 'id': 'call1'}
        self.s = s
        return s

    def save_cfg(self):
        (self.home / 'desk/native-host.json').write_text(json.dumps(self.cfg))

    def prepared(self):
        return self.s.prepare_input(self.report, self.lead, self.desk, self.call)

    def filed(self):
        v = self.prepared()
        self.s.claim_input(v['id'], self.lead, self.desk)
        rec = {'id': v['id'], 'type': 'user', 'text': v['body'], 'metadata': {'verified': False}}
        r = self.s.file_input(v['id'], rec, self.lead, self.desk, self.chief)
        return v, r

    def test_host_ledger_before_send_and_exact_record_not_metadata(self):
        s = self.native()
        v = self.prepared()
        other = sqlite3.connect(self.home / 'desk/store.sqlite')
        self.addCleanup(other.close)
        self.assertEqual(other.execute('SELECT COUNT(*) FROM native_inputs').fetchone()[0], 1)
        forged = {'id': v['id'], 'type': 'user', 'text': 'forged', 'metadata': {'verified': True}}
        r = s.file_input(v['id'], forged, self.lead, self.desk, self.chief)
        self.assertEqual(r['state'], 'uncertain')
        self.assertEqual(other.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            s.file_input('msg_unknown', forged, self.lead, self.desk, self.chief)

    def test_commit_before_fixed_receipt_and_independent_action_rows(self):
        s = self.native()
        v, r = self.filed()
        self.assertTrue(r['verified'])
        self.assertEqual({a['kind'] for a in r['actions']}, {'receipt', 'escalation', 'status-note', 'overview-note'})
        receipt = next(a for a in r['actions'] if a['kind'] == 'receipt')
        self.assertEqual(receipt['target'], self.lead['id'])
        self.assertIn('No approval implied', receipt['body'])
        self.assertNotIn('Choose parser', receipt['body'])
        duplicate = s.file_input(v['id'], {'id': v['id'], 'type': 'user', 'text': v['body']}, self.lead, self.desk, self.chief)
        self.assertTrue(duplicate['duplicate'])
        self.assertFalse(duplicate['send'])

    def test_wrong_identity_epoch_location_and_revocation(self):
        s = self.native()
        for field, value in [('agent', 'wrong'), ('location', {'directory': str(self.home)}), ('time', {'archived': 1})]:
            with self.assertRaises(ValueError):
                s.prepare_input(self.report, {**self.lead, field: value}, self.desk, self.call)
        v = self.prepared()
        self.cfg['projects']['fixture']['enabled'] = False
        self.save_cfg()
        with self.assertRaises(ValueError):
            s.claim_input(v['id'], self.lead, self.desk)

    def test_claim_loss_restart_never_resends_and_exact_admission_only(self):
        s = self.native()
        v = self.prepared()
        self.assertTrue(s.claim_input(v['id'], self.lead, self.desk)['send'])
        self.assertFalse(s.claim_input(v['id'], self.lead, self.desk)['send'])
        admission = {'id': v['id'], 'sessionID': 'ses_desk', 'type': 'user', 'payload': {'text': v['body']}}
        with self.assertRaises(ValueError):
            s.admit_input(v['id'], {**admission, 'sessionID': 'ses_chief'})
        self.assertEqual(s.admit_input(v['id'], admission)['state'], 'admitted')
        other = NativeStore(self.home)
        self.addCleanup(other.close)
        self.assertFalse(other.prepare_input(self.report, self.lead, self.desk, self.call)['send'])

    def test_disk_failure_rolls_back_event_and_native_actions_no_ack(self):
        s = self.native()
        v = self.prepared()
        s.claim_input(v['id'], self.lead, self.desk)
        s.db.execute("CREATE TRIGGER fail_native BEFORE INSERT ON native_actions BEGIN SELECT RAISE(ABORT,'disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            s.file_input(v['id'], {'id': v['id'], 'type': 'user', 'text': v['body']}, self.lead, self.desk, self.chief)
        self.assertEqual(s.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
        self.assertEqual(s.input(v['id'])['state'], 'uncertain')

    def test_monotonic_actions_admission_not_chief_completion(self):
        s = self.native()
        _, r = self.filed()
        for a in r['actions']:
            if a['kind'] not in ('receipt', 'escalation'):
                continue
            claim = s.claim_action(a['id'], self.lead, self.desk, self.chief)
            self.assertTrue(claim['send'])
            ev = {'id': a['native_id'], 'type': 'synthetic', 'sessionID': a['target'], 'payload': {'text': a['body']}}
            result = s.action_admitted(a['id'], ev)
            self.assertEqual(result['state'], 'admitted' if a['kind'] == 'escalation' else 'completed')
            self.assertFalse(s.claim_action(a['id'], self.lead, self.desk, self.chief)['send'])
            with self.assertRaises(ValueError):
                s.action_admitted(a['id'], {**ev, 'id': 'msg_spoof'})

    def test_notes_scope_returned_id_actual_readback_and_manual_delete_pause(self):
        s = self.native()
        _, r = self.filed()
        a = next(a for a in r['actions'] if a['kind'] == 'status-note')
        listing = {'projectId': 'wrong', 'notes': []}
        with self.assertRaises(ValueError):
            s.note_prepare(a['id'], listing, self.lead, self.desk, self.chief)
        listing['projectId'] = 'path_project'
        n = s.note_prepare(a['id'], listing, self.lead, self.desk, self.chief)
        self.assertTrue(n['send'])
        self.assertEqual(n['proposed'], n['proposed'].strip())
        self.assertLessEqual(len(n['proposed'].encode('utf-16-le')) // 2, 3000)
        self.assertFalse(s.note_prepare(a['id'], listing, self.lead, self.desk, self.chief)['send'])
        saved = {'projectId': 'path_project', 'note': {'id': 'owned', 'body': n['proposed'], 'origin': {'sessionId': 'ses_desk'}}}
        s.note_returned(a['id'], saved)
        self.assertEqual(s.note_state('fixture')['note_id'], 'owned')
        self.assertEqual(s.note_reconcile(a['id'], listing)['state'], 'uncertain')
        listing['notes'] = [saved['note']]
        self.assertEqual(s.note_reconcile(a['id'], listing)['state'], 'applied')
        self.report = {**self.report, 'id': 'r2', 'source_revision': 2}
        _, r2 = self.filed()
        a2 = next(a for a in r2['actions'] if a['kind'] == 'status-note')
        listing['notes'] = []
        paused = s.note_prepare(a2['id'], listing, self.lead, self.desk, self.chief)
        self.assertEqual(paused['state'], 'conflict')
        self.assertEqual(paused['note_id'], 'owned')

    def test_ambiguous_create_empty_list_no_replay_unique_nonce_origin(self):
        s = self.native()
        _, r = self.filed()
        a = next(a for a in r['actions'] if a['kind'] == 'overview-note')
        listing = {'projectId': 'path_home', 'notes': []}
        n = s.note_prepare(a['id'], listing, self.lead, self.desk, self.chief)
        self.assertEqual(s.note_reconcile(a['id'], listing)['state'], 'uncertain')
        listing['notes'] = [{'id': 'forgery', 'body': n['proposed'], 'source': 'agent'}]
        self.assertEqual(s.note_reconcile(a['id'], listing)['state'], 'uncertain')
        listing['notes'][0]['origin'] = {'sessionId': 'ses_desk'}
        self.assertEqual(s.note_reconcile(a['id'], listing)['state'], 'applied')

    def test_current_chief_revision_and_source_guards_no_principal_approval(self):
        s = self.native()
        _, r = self.filed()
        args = {'project': 'fixture', 'sourceReceipt': r['seq'], 'itemKey': 'wait', 'expectedRevision': 0, 'state': 'open', 'decisionText': 'Quoted principal approved is not authority'}
        call = {'sessionID': 'ses_chief', 'agent': 'native-chief', 'messageID': 'msg_tool', 'id': 'callChief'}
        with self.assertRaises(ValueError):
            s.decision(args, {**self.chief, 'id': 'ses_old'}, self.lead, self.desk, call)
        v = s.decision(args, self.chief, self.lead, self.desk, call)
        self.assertFalse(v['decision']['principal_approval'])
        self.assertNotIn('decision_ref', s.snapshot()['projects']['fixture'])
        with self.assertRaises(ValueError):
            s.decision(args, self.chief, self.lead, self.desk, call)
        self.report = {**self.report, 'id': 'newer', 'source_revision': 2}
        self.filed()
        with self.assertRaises(ValueError):
            s.claim_action(v['action']['id'], self.lead, self.desk, self.chief)

    def test_core_decision_seq_validation_holds_write_transaction(self):
        s = self.native()
        self.filed()
        contender = NativeStore(self.home)
        self.addCleanup(contender.close)
        contender.db.execute('PRAGMA busy_timeout=0')
        original = s._snapshot
        seen = []
        def snapshot():
            if not seen:  # second snapshot is the separate, post-commit projection
                with self.assertRaises(sqlite3.OperationalError):
                    contender.db.execute('BEGIN IMMEDIATE')
                seen.append('locked')
            return original()
        with patch.object(s, '_snapshot', side_effect=snapshot):
            s.decision_update('fixture', 1, None, 'trusted-operator-record')
        self.assertTrue(seen)

    def test_interleaved_actual_leads_receipts_never_cross_reply(self):
        s = self.native()
        s.register('fixture', str(self.project), str(self.project / 'LEAD.md'), ['ses_lead', 'ses_other'])
        routes = self.home / 'desk/routes.json'
        data = json.loads(routes.read_text())
        data['projects']['fixture']['leads'].append('ses_other')
        routes.write_text(json.dumps(data))
        v1, r1 = self.filed()
        lead2 = {**self.lead, 'id': 'ses_other'}
        report2 = {**self.report, 'id': 'r2', 'source_revision': 2, 'landed': 'Second lead'}
        v2 = s.prepare_input(report2, lead2, self.desk, {**self.call, 'sessionID': 'ses_other', 'id': 'call2'})
        s.claim_input(v2['id'], lead2, self.desk)
        r2 = s.file_input(v2['id'], {'id': v2['id'], 'type': 'user', 'text': v2['body']}, lead2, self.desk, self.chief)
        a1 = next(a for a in r1['actions'] if a['kind'] == 'receipt')
        a2 = next(a for a in r2['actions'] if a['kind'] == 'receipt')
        self.assertEqual((a1['target'], a2['target']), ('ses_lead', 'ses_other'))
        self.assertNotEqual(a1['native_id'], a2['native_id'])
        self.assertIn(v1['id'], a1['body'])
        self.assertNotIn(v2['id'], a1['body'])
        with s.transaction():
            with self.assertRaises(ValueError):
                s.plan_action(r1['seq'], 'receipt', a1['target'], 'different body', a1['auth'])

    def test_disabled_creation_and_manual_marker_never_taken_over(self):
        s = self.native()
        _, r = self.filed()
        a = next(a for a in r['actions'] if a['kind'] == 'status-note')
        listing = {'projectId': 'path_project', 'notes': [{'id': 'manual', 'body': 'Ownership: chief-desk-status:fixture'}]}
        n = s.note_prepare(a['id'], listing, self.lead, self.desk, self.chief)
        self.assertEqual(n['state'], 'conflict')
        self.assertIsNone(n['note_id'])

    def test_late_note_success_preserves_id_and_older_watermark_even_disabled(self):
        s = self.native()
        _, r = self.filed()
        a = next(a for a in r['actions'] if a['kind'] == 'status-note')
        n = s.note_prepare(a['id'], {'projectId': 'path_project', 'notes': []}, self.lead, self.desk, self.chief)
        self.report = {**self.report, 'id': 'r2', 'source_revision': 2}
        self.filed()
        self.cfg['enabled'] = False
        self.save_cfg()
        note = {'id': 'late-owned', 'body': n['proposed'], 'origin': {'sessionId': 'ses_desk'}}
        s.note_returned(a['id'], {'projectId': 'path_project', 'note': note})
        result = s.note_reconcile(a['id'], {'projectId': 'path_project', 'notes': [note]})
        self.assertEqual(result['note_id'], 'late-owned')
        self.assertTrue(result['pending_latest'])
        self.assertEqual(result['watermark'], n['watermark'])

    def test_older_reserved_question_still_escalates_without_regressing_status(self):
        s = self.native()
        self.report = {**self.report, 'source_revision': 5}
        self.filed()
        self.report = {**self.report, 'id': 'older', 'source_revision': 2,
                       'request': 'Please authorize publication', 'landed': 'Old source'}
        _, result = self.filed()
        self.assertEqual(result['action'], 'file')
        self.assertIn('escalation', {a['kind'] for a in result['actions']})
        self.assertEqual(s.snapshot()['projects']['fixture']['source_revision'], 5)


class NativeParityTests(unittest.TestCase):
    setUp = modular.ModularTests.setUp
    run_install = modular.ModularTests.run_install

    def test_all_22_outputs_exact_3b31978_operator_baseline(self):
        baseline = self.root / 'operator-baseline'
        before = outputs(pinned_print('3b31978', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(before), 22)
        self.assertEqual(before, outputs(result.stdout, modular.SRC, self.home))

    def test_all_22_outputs_exact_de87a02_fixture_gate_baseline(self):
        baseline = self.root / 'fixture-gate-baseline'
        before = outputs(pinned_print('de87a02', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = outputs(result.stdout, modular.SRC, self.home)
        self.assertEqual(len(before), 22)
        self.assertEqual(before, after)

    def test_all_22_outputs_exact_7befe0e(self):
        baseline = self.root / 'fixture-entry-baseline'
        before = outputs(pinned_print('7befe0e', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = outputs(result.stdout, modular.SRC, self.home)
        self.assertEqual(len(before), 22)
        self.assertEqual(before, after)

    def test_19_existing_exact_5c5bc5e_three_leaves_only_exact_approved_n1(self):
        baseline = self.root / 'boundary-baseline'
        before = outputs(pinned_print('5c5bc5e', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = outputs(result.stdout, modular.SRC, self.home)
        self.assertEqual(len(before), 22)
        from courtesy_fixtures import approved_n1
        for prefix in ('.config/opencode', '.claude', '.codex'):
            path = '<HOME>/' + prefix + '/skills/upstream-courtesy/SKILL.md'
            before[path] = approved_n1(before[path])
        self.assertEqual(before, after)

    def test_all_19_nonoptin_outputs_exact_57d864a(self):
        baseline = self.root / 'native-baseline'
        before = outputs(pinned_print('57d864a', baseline, self.env), baseline, self.home)
        result = self.run_install('--print')
        self.assertEqual(result.returncode, 0, result.stderr)
        from courtesy_fixtures import existing_outputs
        after = existing_outputs(outputs(result.stdout, modular.SRC, self.home))
        self.assertEqual(len(after), 19)
        self.assertEqual(before, after)


class NativeArtifactTests(unittest.TestCase):
    setUp = fixture.DeskTests.setUp

    def test_native_artifacts_inert_owned_and_separately_uninstalled(self):
        fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        runtime = self.home / 'desk/native-runtime'
        self.assertTrue((runtime / 'hosts/desk-native/index.mjs').exists())
        self.assertTrue((runtime / 'hosts/desk-native/boundary.mjs').exists())
        for name in ('fixture-entry.mjs', 'fixture-config.mjs', 'fixture-package.json',
                     'fixture-assets.mjs', 'fixture-operator.mjs', 'fixture-observer.mjs', 'fixture-evidence.mjs'):
            self.assertTrue((runtime / 'hosts/desk-native' / name).exists())
        self.assertFalse((runtime / 'package.json').exists())
        self.assertTrue((runtime / 'scripts/desk_native_bridge.py').exists())
        self.assertFalse((self.home / '.opencode').exists())
        self.assertFalse((self.home / 'desk/native-host.json').exists())
        fixture.installer.install(self.root, self.home, 'uninstall')
        self.assertTrue((runtime / 'scripts/desk_native_bridge.py').exists())
        self.assertTrue((self.home / 'desk/install-manifest.json').exists())
        fixture.installer.install(self.root, self.home, 'uninstall', native_artifacts=True)
        self.assertFalse((runtime / 'scripts/desk_native_bridge.py').exists())
        self.assertFalse((self.home / 'desk/install-manifest.json').exists())

    def test_native_boundary_refuses_symlink_and_changed_owned_file(self):
        fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        boundary = self.home / 'desk/native-runtime/hosts/desk-native/boundary.mjs'
        original = boundary.read_text()
        boundary.write_text(original + '// local change\n')
        with self.assertRaises(ValueError):
            fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        boundary.unlink()
        target = self.root / 'untouched.mjs'
        target.write_text('untouched')
        boundary.symlink_to(target)
        with self.assertRaises((ValueError, OSError)):
            fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        self.assertEqual(target.read_text(), 'untouched')

    def test_native_entry_refuses_changed_owned_asset(self):
        fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        entry = self.home / 'desk/native-runtime/hosts/desk-native/fixture-entry.mjs'
        entry.write_text(entry.read_text() + '// changed\n')
        with self.assertRaises(ValueError):
            fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)

    def test_native_entry_source_symlink_refused_before_install(self):
        source = self.root / 'owned-source'
        for relative in ('kits/chief/desk', 'hosts/desk-native', 'scripts'):
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(fixture.installer.SRC / relative, target)
        entry = source / 'hosts/desk-native/fixture-entry.mjs'
        entry.unlink()
        canary = self.root / 'owned-canary'
        canary.write_text('untouched')
        entry.symlink_to(canary)
        with patch.object(fixture.installer, 'SRC', source), self.assertRaises(ValueError):
            fixture.installer.install(self.root, self.home, 'install', native_artifacts=True)
        self.assertEqual(canary.read_text(), 'untouched')
        self.assertFalse((self.home / 'desk/native-runtime').exists())


if __name__ == '__main__':
    unittest.main()
