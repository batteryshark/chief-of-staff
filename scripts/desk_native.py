"""Private host bridge library. No public CLI, credentials, transport or model proof flag.

The JS host supplies checked native records over private stdin. Same-user trusted
host code is the boundary, not an OS sandbox. Configuration is operator-owned.
"""
from contextlib import contextmanager
import json
from pathlib import Path
from uuid import uuid4

from desk_store import Store, guard, encoded, fingerprint, now, native_note, utf16_units, resolve_route, timestamp
from install_paths import DestinationRoot


def message_id():
    return 'msg_' + uuid4().hex


class NativeStore(Store):
    def classify(self, report, verified):
        rule = self.registry.get('rules', {}).get(report.get('rule'), {})
        if rule.get('fixture_only') is True:
            # Narrow fixture exception only; production rules/classifier unchanged.
            expected = dict(project='lead-a', id='first-smoke', source_revision=1,
                observed=report.get('observed'), landed='Owned fixture report filed.',
                next='Stop after first smoke.', your_part=None, state='active',
                request='ack', rule='fixture-first-smoke')
            try:
                leads = self.registry['projects']['lead-a']['leads']
                route = resolve_route(self.home, 'lead-a', rule['recipient'])
                valid = (report == expected and leads == [rule['recipient']]
                    and set(rule) == {'id', 'project', 'action', 'active', 'fixture_only',
                        'report_hash', 'recipient', 'epoch', 'answer', 'evidence', 'expires'}
                    and rule['id'] == 'fixture-first-smoke' and rule['action'] == 'ack'
                    and rule['epoch'] == route['epoch'] == 1
                    and rule['answer'] == 'Filed. No approval implied.'
                    and rule['evidence'] == 'trusted-operator-exact-benign-fixture'
                    and timestamp(now()) < timestamp(rule['expires']))
            except (KeyError, ValueError, TypeError):
                valid = False
            if not valid:
                return 'escalate', 'Filed; with chief. No new permission granted.', ['fixture ACK refused']
        return super().classify(report, verified)

    def __init__(self, home):
        super().__init__(home)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS native_inputs(
            id TEXT PRIMARY KEY, report_key TEXT UNIQUE NOT NULL, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS native_actions(
            id TEXT PRIMARY KEY, receipt INTEGER NOT NULL REFERENCES events(seq),
            kind TEXT NOT NULL, state TEXT NOT NULL, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS native_notes(scope TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        self.filing = None

    @contextmanager
    def transaction(self):
        with guard(self.home), self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.registry = json.loads((self.root / 'registry.json').read_text())
            yield

    def config(self):
        p = self.root / 'native-host.json'
        DestinationRoot(self.home).validate_all([p])
        c = json.loads(p.read_text())
        if c.get('version') != 1 or c.get('enabled') is not True:
            raise ValueError('native adapter disabled')
        return c

    def identity(self, record, session, agent, directory):
        if (not isinstance(record, dict) or record.get('id') != session
                or record.get('agent') != agent or record.get('time', {}).get('archived')
                or record.get('location', {}).get('directory') != directory
                or str(Path(directory).resolve()) != directory):
            raise ValueError('native identity/location mismatch')

    def chief(self, record):
        c = self.config()
        p = self.home / 'chief.json'
        DestinationRoot(self.home).validate_all([p])
        chief = json.loads(p.read_text())
        if chief.get('directory') != str(self.home):
            raise ValueError('chief pointer location mismatch')
        self.identity(record, chief['session'], c['chief_agent'], str(self.home))
        if record.get('projectID') != c.get('home_nativeProjectID') or not c.get('home_nativeProjectID'):
            raise ValueError('chief native project mismatch')
        return chief['session']

    def authority(self, project, sender, desk):
        c = self.config()
        p = self.project(project)
        binding = c['projects'][project]
        if binding.get('enabled') is not True:
            raise ValueError('native project disabled')
        self.identity(sender, sender.get('id'), binding['lead_agent'], p['path'])
        if not binding.get('nativeProjectID') or sender.get('projectID') != binding['nativeProjectID']:
            raise ValueError('sender native project mismatch')
        if sender['id'] not in p['leads']:
            raise ValueError('lead revoked')
        route = resolve_route(self.home, project, sender['id'])
        if route['epoch'] < 1 or route['pointer'] != str(self.home / 'desk.json'):
            raise ValueError('native report route not opted in')
        self.identity(desk, route['session'], c['desk_agent'], str(self.home))
        if not c.get('home_nativeProjectID') or desk.get('projectID') != c['home_nativeProjectID']:
            raise ValueError('desk native project mismatch')
        # Native Knowledge scope is explicitly operator-admitted, NOT basename inference.
        if not binding.get('projectId') or not c.get('home_projectId'):
            raise ValueError('native project scope unbound')
        scopes = [v['projectId'] for v in c['projects'].values() if v.get('enabled')]
        if len(set(scopes)) != len(scopes):
            raise ValueError('ambiguous native project namespace collision')
        return {'project': project, 'path': p['path'], 'sender': sender['id'],
                'target': desk['id'], 'epoch': route['epoch'],
                'binding': fingerprint([c, route, p])}

    def audit_native(self, kind, before, after):
        self.db.execute('INSERT INTO changes(kind,created,payload) VALUES(?,?,?)',
                        ('native:' + kind, now(), encoded({'before': before, 'after': after})))

    def input(self, input_id):
        r = self.db.execute('SELECT value FROM native_inputs WHERE id=?', (input_id,)).fetchone()
        if not r:
            raise ValueError('input not host-owned')
        return json.loads(r[0])

    def put_input(self, value, before=None):
        if before is None:
            self.db.execute('INSERT INTO native_inputs VALUES(?,?,?)',
                            (value['id'], value['key'], encoded(value)))
        else:
            self.db.execute('UPDATE native_inputs SET value=? WHERE id=?', (encoded(value), value['id']))
        self.audit_native('input', before, value)

    def prepare_input(self, report, sender, desk, call):
        if not isinstance(report, dict) or len(encoded(report).encode()) > 60000:
            raise ValueError('report exceeds bound')
        self.validate_report(report)
        if set(call) != {'sessionID', 'agent', 'messageID', 'id'} or not all(isinstance(v, str) and v for v in call.values()):
            raise ValueError('actual native tool context required')
        if call['sessionID'] != sender.get('id') or call['agent'] != sender.get('agent'):
            raise ValueError('native tool caller mismatch')
        with self.transaction():
            auth = self.authority(report['project'], sender, desk)
            key = fingerprint([report['project'], report['id']])
            old = self.db.execute('SELECT value FROM native_inputs WHERE report_key=?', (key,)).fetchone()
            if old:
                value = json.loads(old[0])
                if value['report'] != report or value['auth'] != auth:
                    raise ValueError('report id/content/authority conflict')
                return {**value, 'send': False}
            input_id = message_id()
            value = {'id': input_id, 'key': key, 'report': report,
                     'auth': auth, 'call': call, 'state': 'planned', 'receipt': None,
                     'body': encoded({'inputId': input_id, 'desk_report': report}), 'created': now()}
            self.put_input(value)
            return {**value, 'send': True}

    def check_input(self, value, sender, desk):
        if self.authority(value['report']['project'], sender, desk) != value['auth']:
            raise ValueError('input route/epoch/authorization changed')

    def claim_input(self, input_id, sender, desk):
        with self.transaction():
            old = self.input(input_id)
            self.check_input(old, sender, desk)
            if old['state'] != 'planned':
                return {**old, 'send': False}
            value = {**old, 'state': 'uncertain'}
            self.put_input(value, old)  # persisted BEFORE transport; never replay uncertain
            return {**value, 'send': True}

    @staticmethod
    def matches(record, value, inbox=False, kind='user'):
        return (isinstance(record, dict) and record.get('id') == value['id']
                and record.get('type') == kind
                and (record.get('payload', {}).get('text') if inbox else record.get('text')) == value['body']
                and (not inbox or record.get('sessionID') == value['auth']['target']))

    def admit_input(self, input_id, admission):
        with self.transaction():
            old = self.input(input_id)
            if not self.matches(admission, old, inbox=True):
                raise ValueError('native Inbox admission mismatch')
            if old['state'] in ('admitted', 'filed'):
                return old
            if old['state'] != 'uncertain':
                raise ValueError('input not attempted')
            value = {**old, 'state': 'admitted', 'admission': admission}
            self.put_input(value, old)
            return value

    def file_input(self, input_id, record, sender, desk, chief):
        value = self.input(input_id)
        # Only actual owned input records qualify, not c.messageID or metadata hints.
        if not self.matches(record, value):
            return {'state': 'uncertain', 'send': False, 'reason': 'exact active input unavailable/mismatch'}
        self.filing = (value, sender, desk, chief, record)
        try:
            def verify(report, context):
                self.check_input(value, sender, desk)  # inside core transaction+writer guard
                self.chief(chief)
                current = self.input(input_id)
                return current['state'] in ('uncertain', 'admitted', 'filed') and report == current['report']
            result = self.receive(value['report'], {'sender': value['auth']['sender'],
                                  'message_id': input_id, 'project_path': value['auth']['path']}, verify)
            return {**result, 'actions': self.actions(result['seq'])}
        finally:
            self.filing = None

    def _filed(self, seq):
        if not self.filing:
            return
        value, sender, desk, chief, record = self.filing
        row = self.db.execute('SELECT verified FROM events WHERE seq=?', (seq,)).fetchone()
        if not row[0]:
            return  # unverified quarantine has NO native outward actions
        old = self.input(value['id'])
        self.put_input({**old, 'receipt': seq, 'state': 'filed', 'readback': record}, old)
        receipt_body = f'Desk receipt {seq}: filed. No approval implied. Project/overview projection pending. Source input {value["id"]}.'
        self.plan_action(seq, 'receipt', value['auth']['sender'], receipt_body, value['auth'])
        action = self.db.execute('SELECT action FROM audit WHERE seq=?', (seq,)).fetchone()[0]
        # An older milestone cannot replace current status or borrow a routine
        # permission, but its unresolved/reserved question must not disappear.
        if action == 'escalate' or action == 'file' and self.classify(value['report'], True)[0] == 'escalate':
            self.plan_action(seq, 'escalation', chief['id'],
                             f'Desk judgment requested; receipt {seq}. No approval implied.\n' + value['body'], value['auth'])
        # The exact-hash rule gate is retained. Authorized routine prose is NOT
        # smuggled into the universal receipt; proposal/relay is a separate action.
        for kind in ('status-note', 'overview-note'):
            self.plan_action(seq, kind, '', '', value['auth'])

    def plan_action(self, seq, kind, target, body, auth, suffix=''):
        action_id = f'{seq}:{kind}{suffix}'
        value = {'id': action_id, 'receipt': seq, 'kind': kind, 'target': target,
                 'body': body, 'auth': auth, 'native_id': message_id(), 'state': 'planned'}
        old = self.db.execute('SELECT value FROM native_actions WHERE id=?', (action_id,)).fetchone()
        if old:
            previous = json.loads(old[0])
            if any(previous[k] != value[k] for k in ('receipt', 'kind', 'target', 'body', 'auth')):
                raise ValueError('action id conflict')
            return previous
        self.db.execute('INSERT INTO native_actions VALUES(?,?,?,?,?)',
                        (action_id, seq, kind, 'planned', encoded(value)))
        self.audit_native('action', None, value)
        return value

    def actions(self, seq):
        return [json.loads(r[0]) for r in self.db.execute("SELECT value FROM native_actions WHERE receipt=? ORDER BY CASE state WHEN 'planned' THEN 0 WHEN 'uncertain' THEN 1 ELSE 2 END,id LIMIT 32", (seq,))]

    def action(self, action_id):
        row = self.db.execute('SELECT value FROM native_actions WHERE id=?', (action_id,)).fetchone()
        if not row:
            raise ValueError('unknown owned action')
        return json.loads(row[0])

    def put_action(self, old, value):
        self.db.execute('UPDATE native_actions SET state=?,value=? WHERE id=?',
                        (value['state'], encoded(value), value['id']))
        self.audit_native('action', old, value)

    def check_action(self, action, sender, desk, chief):
        auth = self.authority(action['auth']['project'], sender, desk)
        if auth != action['auth']:
            raise ValueError('action revoked/rotated')
        if action['kind'] in ('escalation', 'decision-relay', 'projection-wake'):
            self.chief(chief)
            if action.get('chief', chief['id']) != chief['id']:
                raise ValueError('old chief action')
            if action['kind'] == 'escalation' and action['target'] != chief['id']:
                raise ValueError('chief rotated; no reroute')
        if action['kind'] in ('decision-relay', 'routine-relay'):
            latest = self._snapshot()['projects'].get(auth['project'])
            if not latest or latest['seq'] != action['receipt']:
                raise ValueError('late source relay')
        if action['kind'] == 'decision-relay':
            current = json.loads(self.meta(action['decision_key']) or '{}')
            if current.get('revision') != action['decision_revision'] or current.get('state') == 'revoked':
                raise ValueError('decision superseded/revoked')
        if action['kind'] == 'routine-relay':
            event = self.db.execute('SELECT payload FROM events WHERE seq=?', (action['receipt'],)).fetchone()
            classification, answer, _ = self.classify(json.loads(event[0]), True)
            if classification not in ('ack', 'technical-delegation', 'recorded-relay') or answer != action['body']:
                raise ValueError('routine rule changed/revoked/expired')

    def claim_action(self, action_id, sender, desk, chief):
        with self.transaction():
            old = self.action(action_id)
            self.check_action(old, sender, desk, chief)
            if old['state'] != 'planned':
                return {**old, 'send': False}
            value = {**old, 'state': 'uncertain'}
            self.put_action(old, value)
            return {**value, 'send': True}

    def action_admitted(self, action_id, evidence, inbox=True):
        with self.transaction():
            old = self.action(action_id)
            expected = {'id': old['native_id'], 'body': old['body'], 'auth': {'target': old['target']}}
            if not self.matches(evidence, expected, inbox=inbox, kind='synthetic'):
                raise ValueError('outbound readback mismatch')
            if old['kind'] not in ('receipt', 'escalation', 'decision-relay', 'routine-relay', 'projection-wake'):
                raise ValueError('not a native send action')
            if old['state'] not in ('uncertain', 'admitted', 'completed'):
                raise ValueError('action not attempted')
            if old['state'] in ('completed', 'admitted'):
                return {**old, 'send': False}
            # Completion means native admission ONLY, never execution/human read.
            state = 'admitted' if old['kind'] == 'escalation' else 'completed'
            value = {**old, 'state': state, 'evidence': evidence}
            self.put_action(old, value)
            return value

    def check_send(self, action_id, sender, desk, chief):
        with self.transaction():
            action = self.action(action_id)
            if action['state'] != 'uncertain':
                raise ValueError('action not claimed')
            self.check_action(action, sender, desk, chief)
            return {'current': True}

    def inspect_action(self, action_id, sender, desk, chief):
        with self.transaction():
            action = self.action(action_id)
            self.check_action(action, sender, desk, chief)
            return action

    def propose(self, seq, rule_id, choice, sender, desk, chief):
        if choice != 'apply-exact-recorded-rule':
            raise ValueError('unsupported typed choice')
        with self.transaction():
            row = self.db.execute('SELECT * FROM events WHERE seq=? AND verified=1', (seq,)).fetchone()
            if not row:
                raise ValueError('unknown verified receipt')
            report = json.loads(row['payload'])
            if report['rule'] != rule_id:
                raise ValueError('rule binding mismatch')
            action, answer, _ = self.classify(report, True)
            if action not in ('ack', 'technical-delegation', 'recorded-relay'):
                raise ValueError('no current exact-hash permission')
            auth = self.authority(report['project'], sender, desk)
            result = self.plan_action(seq, 'routine-relay', row['sender'], answer, auth)
            self.check_action(result, sender, desk, chief)
            return result

    def decision(self, args, caller, sender, desk, call):
        with self.transaction():
            chief_id = self.chief(caller)
            if call.get('sessionID') != chief_id or call.get('agent') != caller['agent'] or not call.get('messageID') or not call.get('id'):
                raise ValueError('chief tool provenance missing')
            seq = args['sourceReceipt']
            p = self._snapshot()['projects'].get(args['project'])
            if not p or p['seq'] != seq:
                raise ValueError('late/wrong-project decision')
            auth = self.authority(args['project'], sender, desk)
            source = self.db.execute('SELECT sender FROM events WHERE seq=?', (seq,)).fetchone()[0]
            if source != sender['id']:
                raise ValueError('wrong lead decision')
            key = 'native-decision:' + args['project'] + ':' + args['itemKey']
            previous = json.loads(self.meta(key) or '{"revision":0}')
            if previous['revision'] != args['expectedRevision'] or args['state'] not in ('open', 'closed', 'revoked'):
                raise ValueError('decision revision/state conflict')
            text = args['decisionText']
            if not isinstance(text, str) or not text.strip() or utf16_units(text) > 1000:
                raise ValueError('decision text bound')
            value = {**args, 'revision': previous['revision'] + 1, 'chief': chief_id,
                     'call': call, 'received': now(), 'principal_approval': False}
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, encoded(value)))
            self.audit_native('chief-decision', previous, value)
            # Chief event is judgment, NOT an independently authenticated human ask.
            # Do not populate core decision_ref/your_part as principal-confirmed.
            action = self.plan_action(seq, 'decision-relay', source,
                        f'Chief judgment recorded ({args["state"]}); not principal approval.\n{text}',
                        auth, ':' + fingerprint([key, value['revision']])[:16])
            old = action
            action = {**action, 'chief': chief_id, 'decision_key': key, 'decision_revision': value['revision']}
            self.put_action(old, action)
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('generation', str(self.watermark() + 1)))
            suffix = ':chief-' + fingerprint([key, value['revision']])[:16]
            for kind in ('status-note', 'overview-note'):
                self.plan_action(seq, kind, '', '', auth, suffix)
            wake = self.plan_action(seq, 'projection-wake', desk['id'],
                    f'Desk projection pending after chief judgment. Use desk_project_sync({seq}). No approval implied.', auth, suffix)
            self.put_action(wake, {**wake, 'chief': chief_id})
            return {'decision': value, 'action': action, 'wake': self.action(wake['id'])}

    def smoke_state(self, input_id):
        """Bounded private readback, never a model tool or recovery operation."""
        with self.transaction():
            value = self.input(input_id)
            if (value['report']['project'] != 'lead-a'
                    or self.registry.get('rules', {}).get('fixture-first-smoke', {}).get('fixture_only') is not True):
                raise ValueError('fixture-only ledger readback')
            seq = value['receipt']
            counts = {table: self.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                      for table in ('native_inputs', 'native_actions', 'native_notes', 'events')}
            if counts != dict(native_inputs=1, native_actions=3, native_notes=2, events=1):
                raise ValueError('not an isolated first-smoke ledger')
            event = self.db.execute('SELECT * FROM events WHERE seq=?', (seq,)).fetchone()
            return {'input': value, 'actions': self.actions(seq),
                    'notes': {r['scope']: json.loads(r['value']) for r in self.db.execute('SELECT * FROM native_notes')},
                    'event': {**dict(event), 'payload': json.loads(event['payload'])},
                    'snapshot': self._snapshot(), 'watermark': self.watermark(), 'counts': counts}

    def pending(self):
        # Fixed bound; no scanning unrelated sessions or native knowledge.
        return {'inputs': [json.loads(r[0]) for r in self.db.execute('SELECT value FROM native_inputs ORDER BY rowid DESC LIMIT 32')],
                'actions': [json.loads(r[0]) for r in self.db.execute("SELECT value FROM native_actions WHERE state IN ('uncertain','admitted') ORDER BY rowid LIMIT 32")],
                'pending_action_count': self.db.execute("SELECT COUNT(*) FROM native_actions WHERE state!='completed'").fetchone()[0]}

    def note_state(self, scope):
        row = self.db.execute('SELECT value FROM native_notes WHERE scope=?', (scope,)).fetchone()
        return json.loads(row[0]) if row else {'state': 'missing', 'note_id': None, 'body': None}

    def put_note(self, scope, before, value):
        self.db.execute('INSERT OR REPLACE INTO native_notes VALUES(?,?)', (scope, encoded(value)))
        self.audit_native('note:' + scope, before, value)

    def scope(self, action):
        c = self.config()
        if action['kind'] == 'status-note':
            project = action['auth']['project']
            return project, self.project(project)['path'], c['projects'][project]['projectId']
        if action['kind'] == 'overview-note':
            return '@overview', str(self.home), c['home_projectId']
        raise ValueError('not a Note action')

    def listed(self, listing, project_id):
        if (not isinstance(listing, dict) or listing.get('projectId') != project_id
                or not isinstance(listing.get('notes'), list) or len(listing['notes']) > 200):
            raise ValueError('native Knowledge scope/list mismatch')
        return listing['notes']

    def overview_body(self, snapshot):
        def plain(v):
            # Inert summary, no lead-supplied links or heading/ownership injection.
            import re
            return re.sub(r'([\\`*_{}\[\]()<>!#])', r'\\\1', ' '.join(str(v).split()))
        rows = sorted(snapshot['projects'].items(), key=lambda kv: (not bool(kv[1]['your_part']), kv[0]))
        head = ('Chief desk — overview\nWarning: reported snapshots, not live completion; UI visibility unproved.\n'
                f'Your part: see with-chief requests below; no principal approval inferred.\n'
                f'Missing sources: {len(snapshot["missing"])}; unverified: {snapshot["quarantined"]}.\n')
        lines = []
        for key, row in rows:
            line = (f'{plain(key)}: landed {plain(row["landed"])} · next {plain(row["next"])} · '
                    f'your part {plain(row["your_part"] or "unknown")} (with chief, not confirmed asked); '
                    f'observed {plain(row["observed"])}; received {row["received"]}; receipt {row["seq"]}.')
            if utf16_units(head + '\n'.join(lines + [line])) > 2400:
                break
            lines.append(line)
        return native_note(head + '\n'.join(lines) +
                           f'\nOmitted sources: {len(rows) - len(lines)}; stale age must be checked against observed times. '
                           f'Full source: per-project panels and desk/store.sqlite. Watermark {snapshot["watermark"]}.')

    def note_prepare(self, action_id, listing, sender, desk, chief):
        with self.transaction():
            action = self.action(action_id)
            self.check_action(action, sender, desk, chief)
            scope, directory, project_id = self.scope(action)
            notes = self.listed(listing, project_id)
            old = self.note_state(scope)
            if action['state'] != 'planned' or old['state'] in ('uncertain', 'conflict'):
                return {**old, 'send': False}
            if old.get('note_id'):
                matches = [n for n in notes if n.get('id') == old['note_id']]
                if len(matches) != 1 or matches[0].get('body') != old['body']:
                    value = {**old, 'state': 'conflict', 'reason': 'manual edit/deletion; pause, never recreate'}
                    self.put_note(scope, old, value)
                    return {**value, 'send': False}
            elif any('Ownership: chief-desk-status:' + scope in n.get('body', '') for n in notes):
                value = {**old, 'state': 'conflict', 'reason': 'existing marker is not ownership; explicit transfer required'}
                self.put_note(scope, old, value)
                return {**value, 'send': False}
            if not old.get('note_id'):
                permission = self.config().get('overview_create') if scope == '@overview' else self.config()['projects'][scope].get('note_create')
                if permission is not True:
                    return {**old, 'send': False, 'reason': 'owned Note creation not explicitly admitted'}
            snap = self._snapshot()  # same BEGIN IMMEDIATE snapshot as action/ownership
            allowed = {key for key, value in self.config()['projects'].items() if value.get('enabled') is True}
            snap['projects'] = {key: value for key, value in snap['projects'].items() if key in allowed}
            snap['missing'] = [key for key in snap['missing'] if key in allowed]
            if old['state'] == 'applied' and old.get('watermark') == snap['watermark']:
                self.put_action(action, {**action, 'state': 'completed', 'note_id': old['note_id'],
                                         'watermark': old['watermark'], 'coalesced': True})
                return {**old, 'send': False}
            nonce = uuid4().hex
            body = self.overview_body(snap) if scope == '@overview' else self.knowledge_body(scope, snapshot=snap)
            judgments = []
            for row in self.db.execute("SELECT value FROM meta WHERE key LIKE 'native-decision:%' ORDER BY key LIMIT 64"):
                judgment = json.loads(row[0])
                current = snap['projects'].get(judgment['project'])
                if (current and current['seq'] == judgment['sourceReceipt'] and judgment['chief'] == chief['id']
                        and (scope == '@overview' or judgment['project'] == scope)):
                    # Do not quote arbitrary decision prose as an approval/ask.
                    judgments.append(f'{judgment["project"]}: {judgment["state"]}, source receipt {judgment["sourceReceipt"]}, revision {judgment["revision"]}')
            if judgments:
                body += '\nChief judgment events (not principal asks/approval): ' + '; '.join(judgments[:3])
                if len(judgments) > 3:
                    body += f'; {len(judgments) - 3} omitted; full journal retained.'
            # Reserve room for a host nonce without truncating core provenance.
            body = native_note(body + '\nNative intent: ' + nonce)
            if utf16_units(body) > 3000:
                return {**old, 'send': False, 'reason': 'Note plus native provenance exceeds bound; pending'}
            value = {**old, 'state': 'uncertain', 'action': action_id, 'scope': scope,
                     'directory': directory, 'projectId': project_id, 'proposed': body,
                     'expected': old['body'], 'nonce': nonce, 'watermark': snap['watermark'],
                     'creator': desk['id'], 'before_ids': [n['id'] for n in notes]}
            self.put_note(scope, old, value)
            self.put_action(action, {**action, 'state': 'uncertain', 'scope': scope, 'nonce': nonce})
            return {**value, 'send': True}

    def note_returned(self, action_id, saved):
        # Retain returned ID immediately, even if subsequent list/read fails.
        with self.transaction():
            a = self.action(action_id)
            scope = '@overview' if a['kind'] == 'overview-note' else a['auth']['project']
            old = self.note_state(scope)
            note = saved.get('note', {})
            if (old.get('action') != action_id or old['state'] != 'uncertain'
                    or saved.get('projectId') != old.get('projectId') or not note.get('id')
                    or note.get('body') != old['proposed']
                    or old.get('note_id') not in (None, note['id'])):
                raise ValueError('saved Note scope/id/body conflict')
            value = {**old, 'note_id': note['id'], 'returned': saved}
            self.put_note(scope, old, value)
            return value

    def note_reconcile(self, action_id, listing):
        with self.transaction():
            a = self.action(action_id)
            scope = '@overview' if a['kind'] == 'overview-note' else a['auth']['project']
            old = self.note_state(scope)
            notes = self.listed(listing, old.get('projectId'))
            if old.get('action') != action_id or old['state'] != 'uncertain':
                return {**old, 'send': False}
            if old.get('note_id'):
                matches = [n for n in notes if n.get('id') == old['note_id'] and n.get('body') == old['proposed']]
            else:
                # Exact nonce/body + actual native origin + absence before intent:
                # a marker/title/source:agent alone is NEVER sufficient ownership.
                matches = [n for n in notes if n.get('id') not in old['before_ids']
                           and n.get('body') == old['proposed']
                           and n.get('origin', {}).get('sessionId') == old['creator']]
            if len(matches) != 1:
                return {**old, 'send': False, 'reason': 'ambiguous/missing readback; no replay permission'}
            actual = matches[0]
            value = {**old, 'state': 'applied', 'note_id': actual['id'],
                     'body': actual['body'], 'readback': actual,
                     'pending_latest': old['watermark'] != self.watermark()}
            self.put_note(scope, old, value)
            self.put_action(a, {**a, 'state': 'completed', 'note_id': actual['id'],
                               'watermark': old['watermark'], 'pending_latest': value['pending_latest']})
            return value


def dispatch(store, op, args):
    """Closed private protocol; never exported as a model/operator-shell tool."""
    methods = {
        'prepare_input': store.prepare_input, 'claim_input': store.claim_input,
        'admit_input': store.admit_input, 'file_input': store.file_input,
        'input': store.input, 'actions': store.actions, 'action': store.action,
        'claim_action': store.claim_action, 'action_admitted': store.action_admitted,
        'check_send': store.check_send,
        'inspect_action': store.inspect_action,
        'propose': store.propose, 'decision': store.decision, 'pending': store.pending,
        'note_prepare': store.note_prepare, 'note_returned': store.note_returned,
        'note_reconcile': store.note_reconcile, 'smoke_state': store.smoke_state,
    }
    if op not in methods or not isinstance(args, dict):
        raise ValueError('unsupported host operation')
    try:
        return methods[op](**args)
    except Exception:
        # Refusal is not an ACK. Keep a bounded provenance-only rejection audit
        # when durable storage remains available; never echo arbitrary report text.
        try:
            store.db.rollback()
            with store.db:
                store.db.execute('BEGIN IMMEDIATE')
                correlation = {key: str(args[key])[:200] for key in ('input_id', 'action_id', 'seq') if key in args}
                store.audit_native('rejected:' + op, None, correlation)
        except Exception:
            pass  # disk failure cannot turn into success or outward action
        raise
