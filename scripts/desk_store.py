"""Offline desk foundations. No network, process execution, scheduling or host identity API.

SQLite FULL transactions are the authoritative receipt/audit/outbox journal. Files are
rebuildable projections. Only a trusted in-process host verifier can admit a report;
the CLI deliberately has no 'verified' switch. Local operators remain trusted.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from uuid import UUID

from install_paths import DestinationRoot


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def utf16_units(value):
    """Native managed-tool bounds use JavaScript String.length, not codepoints."""
    return len(value.encode('utf-16-le', errors='surrogatepass')) // 2


def native_note(value):
    # ECMAScript trim whitespace, deliberately not Python's broader str.strip.
    whitespace = '\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
    return value.strip(whitespace)


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', value):
        raise ValueError('invalid stable id')
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('timestamp must include zone')
    return date.timestamp()


def atomic(path, text):
    """Caller holds the shared writer lock. Preflight is not a sandbox/race defense."""
    path = Path(path)
    DestinationRoot(path.parent).validate_all([path])
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def guard(home):
    """Shared by chief-section updates and desk projections. No stale-lock deletion."""
    lock = Path(home) / 'desk' / 'writer.lock'
    DestinationRoot(home).validate_all([lock])
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, encoded({'pid': os.getpid(), 'created': now()}).encode())
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        lock.unlink()


def section(text, name):
    matches = list(re.finditer(r'^## ' + re.escape(name) + r'\s*\n', text, re.M))
    if len(matches) != 1:
        raise ValueError('missing or ambiguous section')
    start = matches[0].end()
    end = re.search(r'^## ', text[start:], re.M)
    return start, start + end.start() if end else len(text)


def revision(text):
    return hashlib.sha256(text.encode()).hexdigest()


def guarded_section(home, name, expected_revision, expected_body, replacement):
    """Chief's cooperative writer, never used by a lead-report action."""
    if name not in ('Priorities', 'Decisions', 'Stop conditions', 'Parked'):
        raise ValueError('not a chief-owned brief section')
    with guard(home):
        require_protocol(home)
        path = Path(home) / 'brief.md'
        DestinationRoot(home).validate_all([path])
        text = path.read_text()
        a, b = section(text, name)
        if revision(text) != expected_revision or text[a:b] != expected_body:
            raise ValueError('brief conflict; reread, never restore old file')
        if re.search(r'^## ', replacement, re.M):
            raise ValueError('replacement cannot introduce sections')
        atomic(path, text[:a] + replacement + text[b:])
        return revision(path.read_text())


def require_protocol(home):
    path = Path(home) / 'desk' / 'writer-protocol.json'
    DestinationRoot(home).validate_all([path])
    config = json.loads(path.read_text())
    if config != {'version': 1, 'chief': True, 'desk': True}:
        raise ValueError('cooperative writer protocol not configured')


class Store:
    def __init__(self, home):
        self.home = Path(home)
        if not self.home.is_absolute() or self.home.resolve() != self.home:
            raise ValueError('chief home must be canonical absolute path')
        self.root = self.home / 'desk'
        DestinationRoot(self.home).validate_all([
            self.root / name for name in ('store.sqlite', 'store.sqlite-journal',
                                         'registry.json', 'writer.lock', 'progress.html',
                                         'snapshot.json', 'summary.md', 'projection.json')])
        if not self.root.is_dir():
            raise ValueError('install desk explicitly first')
        self.registry = json.loads((self.root / 'registry.json').read_text())
        if self.registry.get('version') != 1:
            raise ValueError('unsupported registry')
        self.db = sqlite3.connect(self.root / 'store.sqlite', timeout=1)
        os.chmod(self.root / 'store.sqlite', 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY, project TEXT NOT NULL, report_id TEXT NOT NULL,
              transport_id TEXT NOT NULL UNIQUE, sender TEXT NOT NULL, digest TEXT NOT NULL,
              received TEXT NOT NULL, verified INTEGER NOT NULL, payload TEXT NOT NULL,
              context TEXT NOT NULL,
              UNIQUE(project,report_id));
            CREATE TABLE IF NOT EXISTS audit(
              seq INTEGER PRIMARY KEY REFERENCES events(seq), action TEXT NOT NULL,
              answer TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(
              seq INTEGER PRIMARY KEY REFERENCES events(seq), target TEXT NOT NULL,
              state TEXT NOT NULL, message_id TEXT, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,
              created TEXT NOT NULL,payload TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def project(self, name):
        row = self.registry.get('projects', {}).get(ident(name))
        if not row:
            raise ValueError('unregistered project')
        return row

    def register(self, name, project, log, leads):
        """Trusted operator administration; never called by receive or model output."""
        ident(name)
        project, log = Path(project), Path(log)
        if not project.is_absolute() or project.resolve() != project or not project.is_dir():
            raise ValueError('approved project must exist at its canonical path')
        if not log.is_absolute() or log.parent != project or log.name != 'LEAD.md':
            raise ValueError('approved log must be project LEAD.md')
        DestinationRoot(project).validate_all([log])
        if not leads or any(not re.fullmatch(r'ses_[A-Za-z0-9]+', lead) for lead in leads):
            raise ValueError('explicit lead identities required')
        with guard(self.home):
            self.registry = json.loads((self.root / 'registry.json').read_text())
            self.registry.setdefault('projects', {})[name] = {
                'path': str(project), 'log': str(log), 'leads': leads}
            atomic(self.root / 'registry.json', encoded(self.registry) + '\n')

    def add_rule(self, rule):
        """Operator/Strong-reviewed exact-intent proof, NOT a model permission label.

        Exact report binding is deliberately conservative until semantic evaluation
        and actual host attribution are proven. A changed sentence invalidates it.
        """
        self.project(rule['project'])
        if rule['action'] not in ('ack', 'technical-delegation', 'recorded-relay'):
            raise ValueError('routine action not allowed')
        if not rule.get('evidence') or not re.fullmatch(r'[0-9a-f]{64}', rule['report_hash']):
            raise ValueError('Strong-reviewed intent hash and evidence required')
        timestamp(rule['expires'])
        if type(rule.get('active')) is not bool or not isinstance(rule.get('evidence'), str):
            raise ValueError('explicit active status and evidence required')
        with guard(self.home):
            self.registry = json.loads((self.root / 'registry.json').read_text())
            self.registry.setdefault('rules', {})[ident(rule['id'])] = rule
            atomic(self.root / 'registry.json', encoded(self.registry) + '\n')

    @staticmethod
    def validate_report(report):
        required = {'project', 'id', 'source_revision', 'observed', 'landed', 'next',
                    'your_part', 'state', 'request', 'rule'}
        if not isinstance(report, dict) or set(report) != required:
            raise ValueError('invalid report schema')
        ident(report['project'])
        if not isinstance(report['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', report['id']):
            raise ValueError('invalid report id')
        if type(report['source_revision']) is not int or report['source_revision'] < 0:
            raise ValueError('source revision must be nonnegative integer')
        timestamp(report['observed'])
        if timestamp(report['observed']) > timestamp(now()) + 60:
            raise ValueError('future observation')
        if report['state'] not in ('active', 'paused', 'waiting'):
            raise ValueError('invalid work state')
        if any(not isinstance(report[k], str) or len(report[k]) > 10000
               for k in ('landed', 'next', 'request', 'rule')):
            raise ValueError('invalid report text')
        if report['your_part'] is not None and not isinstance(report['your_part'], str):
            raise ValueError('invalid waiting state')

    def receive(self, report, context, verifier=None):
        """Persist before reply. Context is a hint without a trusted host verifier.

        CLI supplies no verifier; native subclass binds actual records and ledger.
        """
        self.validate_report(report)
        if not isinstance(context, dict) or set(context) != {'sender', 'message_id', 'project_path'}:
            raise ValueError('transport context hint required')
        if any(not isinstance(v, str) or not v or len(v) > 1000 for v in context.values()):
            raise ValueError('invalid transport context')
        digest = fingerprint(report)
        with guard(self.home), self.db:
            self.db.execute('BEGIN IMMEDIATE')
            # Registry/rule changes use this same guard, preventing a stale
            # revocation decision between classification and receipt commit.
            self.registry = json.loads((self.root / 'registry.json').read_text())
            project = self.registry.get('projects', {}).get(report['project'])
            verified = bool(project and context['sender'] in project['leads']
                            and context['project_path'] == project['path']
                            and verifier and verifier(report, context) is True)
            old = self.db.execute('SELECT * FROM events WHERE transport_id=? OR (project=? AND report_id=?)',
                                  (context['message_id'], report['project'], report['id'])).fetchall()
            if old:
                old_context = json.loads(old[0]['context'])
                if (len(old) != 1 or old[0]['digest'] != digest
                        or old_context['sender'] != context['sender']
                        or old_context['project_path'] != context['project_path']
                        or bool(old[0]['verified']) != verified):
                    raise ValueError('id/content or sender conflict')
                return {**self.receipt(old[0]['seq']), 'duplicate': True, 'send': False}
            action, answer, evidence = self.classify(report, verified)
            latest = self.db.execute('SELECT payload FROM events WHERE project=? AND verified=1 ORDER BY seq DESC', (report['project'],)).fetchall()
            if verified and any(json.loads(r[0])['source_revision'] >= report['source_revision'] for r in latest):
                action, answer, evidence = 'file', 'Filed older report; current status unchanged.', ['out-of-order source']
            cursor = self.db.execute('INSERT INTO events(project,report_id,transport_id,sender,digest,received,verified,payload,context) VALUES(?,?,?,?,?,?,?,?,?)',
                                     (report['project'], report['id'], context['message_id'], context['sender'], digest, now(), int(verified), encoded(report), encoded(context)))
            seq = cursor.lastrowid
            self.db.execute('INSERT INTO audit VALUES(?,?,?,?)', (seq, action, answer, encoded(evidence)))
            # Unverified sender is never an outward target. Escalation is a plan,
            # not transport admission and not a chief conversation mutation.
            target = context['sender'] if action in ('file', 'ack', 'technical-delegation', 'recorded-relay') else 'chief.json'
            self.db.execute('INSERT INTO outbox VALUES(?,?,?,?,?)', (seq, target, 'planned', None, 'no transport invoked'))
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('generation', str(self.watermark() + 1)))
            self._filed(seq)
        # Transaction committed with FULL sync before projections or receipt.
        try:
            self.project_files()
        except (OSError, ValueError) as error:
            self.set_meta('projection_error', str(error))
        return self.receipt(seq)

    def _filed(self, seq):
        """Host subclass hook inside the filing transaction; never model supplied."""

    def classify(self, report, verified):
        if not verified:
            return 'quarantine', 'Filed unverified report; with chief for attribution.', ['identity unproven']
        rule = self.registry.get('rules', {}).get(report['rule'], {})
        applicable = (rule.get('project') == report['project']
                      and rule.get('report_hash') == fingerprint(report)
                      and rule.get('active') is True and rule.get('evidence')
                      and timestamp(rule.get('expires', '1970-01-01T00:00:00Z')) > timestamp(now()))
        action = rule.get('action') if applicable else None
        if action not in ('ack', 'technical-delegation', 'recorded-relay'):
            return 'escalate', 'Filed; with chief. No new permission granted.', ['uncertain or no applicable reviewed rule']
        answers = {'ack': 'Filed. No approval implied.',
                   'technical-delegation': 'Filed. Technical, your call within the recorded scope; log your decision.',
                   'recorded-relay': 'Filed. Recorded decision: ' + rule.get('decision', '')}
        if action == 'recorded-relay' and (not rule.get('decision') or not rule.get('decision_ref')):
            return 'escalate', 'Filed; with chief for decision provenance.', ['missing decision provenance']
        return action, answers[action], [rule['id'], rule['evidence'], rule.get('decision_ref')]

    def receipt(self, seq):
        row = self.db.execute('SELECT e.*,a.action,a.answer,a.evidence,o.state AS delivery FROM events e JOIN audit a USING(seq) JOIN outbox o USING(seq) WHERE seq=?', (seq,)).fetchone()
        if row is None:
            raise ValueError('unknown receipt')
        cache_pending = self.meta('projected') != str(self.watermark())
        canvas_pending = self.projection().get('canvas_pending', True)
        brief_pending = bool(self.meta('brief_pending'))
        project_id = row['project']
        knowledge = self.knowledge_state(project_id)
        knowledge_pending = (knowledge.get('state') != 'applied'
                             or knowledge.get('watermark') != self.watermark()
                             or knowledge.get('todo_intent') is not None)
        return {'seq': seq, 'action': row['action'], 'answer': row['answer'],
                'verified': bool(row['verified']), 'delivery': row['delivery'],
                'cache_pending': cache_pending, 'canvas_pending': canvas_pending,
                'knowledge_pending': knowledge_pending, 'brief_pending': brief_pending,
                'sync_pending': cache_pending or knowledge_pending or brief_pending}

    def watermark(self):
        return int(self.meta('generation') or '0')

    def meta(self, key):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, value))
            if key in ('brief_audit', 'brief_pending', 'projection_error') or key.startswith('knowledge:'):
                self.db.execute('INSERT INTO changes(kind,created,payload) VALUES(?,?,?)', (key, now(), value))

    def delivery(self, seq, state, message_id=None, detail=''):
        allowed = {'planned': {'admitted', 'uncertain'}, 'admitted': {'completed', 'uncertain'},
                   'uncertain': {'completed'}, 'completed': set()}
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM outbox WHERE seq=?', (seq,)).fetchone()
            if not row or state not in allowed[row['state']]:
                raise ValueError('delivery transition refused; no blind replay')
            if state in ('admitted', 'completed') and not (message_id or row['message_id']):
                raise ValueError('native message id required')
            if message_id and row['message_id'] and message_id != row['message_id']:
                raise ValueError('native correlation conflict')
            self._delivery_transition(row, state, message_id, detail)

    def _delivery_transition(self, row, state, message_id, detail):
        """Caller holds BEGIN IMMEDIATE; audit and mutation commit together."""
        after = dict(row)
        after.update(state=state, message_id=message_id or row['message_id'],
                     detail='\n'.join(v for v in (row['detail'], detail) if v))
        self.db.execute('UPDATE outbox SET state=?,message_id=?,detail=? WHERE seq=?',
                        (after['state'], after['message_id'], after['detail'], row['seq']))
        self.db.execute('INSERT INTO changes(kind,created,payload) VALUES(?,?,?)',
                        ('delivery', now(), encoded({'before': dict(row), 'after': after})))

    def recover_delivery(self):
        # Even a planned send may have happened before its admission was saved.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            rows = self.db.execute("SELECT * FROM outbox WHERE state IN ('planned','admitted')").fetchall()
            for row in rows:
                self._delivery_transition(row, 'uncertain', None,
                                          'restart: inspect native ids before any action')

    def snapshot(self):
        self.db.execute('BEGIN')
        try:
            return self._snapshot()
        finally:
            self.db.commit()

    def _snapshot(self):
        rows = self.db.execute('SELECT e.*,a.action,a.answer,a.evidence FROM events e JOIN audit a USING(seq) ORDER BY seq').fetchall()
        projects = {}
        for row in rows:
            report = json.loads(row['payload'])
            old = projects.get(row['project'])
            if not row['verified']:
                continue
            if old and report['source_revision'] <= old['source_revision']:
                continue
            projects[row['project']] = {**report, 'seq': row['seq'], 'received': row['received'],
                                        'action': row['action'], 'answer': row['answer'],
                                        'evidence': json.loads(row['evidence'])}
        for name, project in projects.items():
            decision = self.meta('decision:' + name)
            decision = json.loads(decision) if decision else None
            if decision and decision['source_seq'] == project['seq']:
                project.update(your_part=decision['your_part'], decision_ref=decision['reference'],
                               decision_received=decision['received'])
        return {'watermark': self.watermark(), 'assembled': now(), 'projects': projects,
                'missing': sorted(set(self.registry.get('projects', {})) - set(projects)),
                'brief_pending': bool(self.meta('brief_pending')),
                'quarantined': sum(not row['verified'] for row in rows)}

    def project_files(self):
        with guard(self.home):
            snapshot = self.snapshot()
            DestinationRoot(self.home).validate_all([self.root / 'projects'])
            projects_dir = self.root / 'projects'
            projects_dir.mkdir(mode=0o700, exist_ok=True)
            for name in self.registry.get('projects', {}):
                ident(name)
                directory = projects_dir / name
                DestinationRoot(self.home).validate_all([directory / 'digest.md'])
                directory.mkdir(mode=0o700, exist_ok=True)
                events = self.db.execute('SELECT e.seq,e.received,e.verified,e.payload,a.action FROM events e JOIN audit a USING(seq) WHERE project=? ORDER BY e.seq', (name,)).fetchall()
                text = f'# {name}: filed milestones\n\nWatermark: {snapshot["watermark"]}\n'
                for event in events:
                    r = json.loads(event['payload'])
                    text += f'\n- Receipt {event["seq"]} · {event["received"]} · {event["action"]} · source revision {r["source_revision"]}\n  Lead reported: {r["landed"]}\n'
                atomic(directory / 'digest.md', text)
            atomic(self.root / 'snapshot.json', encoded(snapshot) + '\n')
            summary = '# Desk digest\n\nWatermark: ' + str(snapshot['watermark']) + '\n'
            for name, project in snapshot['projects'].items():
                summary += f'\n- {name}: {project["landed"]}\n  Next: {project["next"]}\n  Your part: {project["your_part"] or "Unknown; none confirmed"} · {project["action"]}\n'
            for name in snapshot['missing']:
                summary += f'\n- {name}: missing verified report; landed/next/your part unknown.\n'
            summary += f'\nUnverified receipts: {snapshot["quarantined"]}. See journal/audit; not current progress.\n'
            atomic(self.root / 'summary.md', summary)
            atomic(self.root / 'progress.html', render_view(snapshot))
            previous = self.projection()
            previous.update({'cache_watermark': snapshot['watermark'],
                             'canvas_pending': previous.get('canvas_watermark') != snapshot['watermark']})
            atomic(self.root / 'projection.json', encoded(previous) + '\n')
            self.set_meta('projected', str(snapshot['watermark']))
            self.set_meta('projection_error', '')
            return snapshot

    def projection(self):
        path = self.root / 'projection.json'
        return json.loads(path.read_text()) if path.exists() else {'view_id': None, 'revision': None, 'canvas_watermark': None}

    def knowledge_state(self, project_id):
        value = self.meta('knowledge:' + project_id)
        return json.loads(value) if value else {'state': 'missing', 'note_id': None, 'body': None, 'todos': {}}

    def knowledge_body(self, project_id, projected=None, snapshot=None):
        """Deterministic per-project status note. Plan ownership stays with lead."""
        self.project(project_id)
        snapshot = snapshot if snapshot is not None else self.snapshot()
        p = snapshot['projects'].get(project_id)
        def plain(value):
            # Keep lead prose inert in a Markdown note: no remote image/link,
            # injected heading, HTML or forged first-line ownership marker.
            value = ' '.join(str(value).split())
            return re.sub(r'([\\`*_{}\[\]()<>!#])', r'\\\1', value)
        marker = f'Ownership: chief-desk-status:{project_id}'
        projected = projected or now()
        title = f'{project_id} — project status'
        if not p:
            return native_note(f'{title}\nWarning: missing verified report; namespace/visibility pending.\n'
                               f'Your part: Unknown\n{marker}\nLanded: Unknown\nNext: Unknown\n'
                               f'Source/received: unknown. Projected {projected}.')
        part = p['your_part'] or 'Unknown; no current request confirmed'
        if p['your_part'] and not p.get('decision_ref'):
            part = 'With chief (not confirmed asked): ' + part
        age = 'Older source' if timestamp(projected) - timestamp(p['observed']) > 86400 else 'Reported snapshot'
        prefix = (f'{title}\nWarning: {age}; namespace/visibility pending.\n'
                  f'Your part: {plain(part)}\n{marker}\n')
        suffix = (f'\nLead report {plain(p["id"])}; observed {plain(p["observed"])}; received {p["received"]}.\n'
                  f'Source receipt {p["seq"]}; {p["action"]}; journal desk/store.sqlite events seq={p["seq"]}. '
                  f'Chief update: {plain(p.get("decision_ref", "none confirmed"))}.\n'
                  f'Projected {projected}; watermark {snapshot["watermark"]}.')
        landed, next_step = plain(p['landed']), plain(p['next'])
        body = native_note(prefix + f'Landed: {landed}\nNext: {next_step}' + suffix)
        if utf16_units(body) <= 3000:
            return body
        # Only summaries may be shortened. Never cut your-part, provenance or source
        # references; the full event remains durable even if no minimal note fits.
        notice = '\nSummaries truncated; full source retained in journal above.'
        base = native_note(prefix + 'Landed: \nNext: ' + suffix + notice)
        available = 3000 - utf16_units(base)
        if available < 0:
            raise ValueError('native Note minimum exceeds 3000 UTF-16 units; projection pending')
        def shortened(value, budget):
            # Tokenize escaped Markdown pairs so truncation cannot leave a lone slash.
            result = ''
            for token in re.findall(r'\\.|[^\\]', value, re.S):
                if utf16_units(result + token) > budget:
                    break
                result += token
            return result
        return native_note(prefix + 'Landed: ' + shortened(landed, available // 2) +
                           '\nNext: ' + shortened(next_step, available - available // 2) + suffix + notice)

    def knowledge_prepare(self, project_id):
        """Persist one operation intent; no native call. Repeated creates are blocked.

        Future adapter must knowledge.list in the exact registered project first,
        reconcile the owned marker/id, and use expected=old body on note updates.
        No native updatedAt/order/pin/CAS assumptions. Todos staged separately.
        """
        self.project(project_id)
        with guard(self.home):
            current = self.knowledge_state(project_id)
            if current['state'] in ('planned', 'uncertain', 'conflict'):
                return {**current, 'send': False, 'reason': 'reconcile existing intent; no blind create/retry'}
            if (current['state'] == 'applied' and current.get('note_id')
                    and current.get('watermark') == self.watermark()):
                return {**current, 'send': False}
            projected = now()
            snapshot = self.snapshot()
            try:
                body = self.knowledge_body(project_id, projected, snapshot)
            except ValueError as error:
                pending = {**current, 'state': 'pending', 'reason': str(error), 'pending_latest': True}
                self.set_meta('knowledge:' + project_id, encoded(pending))
                return {**pending, 'send': False}
            intent = {**current, 'state': 'planned', 'intent': fingerprint([project_id, body, snapshot['watermark']]),
                       'projected': projected, 'native_scope': None, 'visibility': 'pending',
                      'project': project_id, 'path': self.project(project_id)['path'],
                      'operation': 'update-note' if current.get('note_id') else 'create-note',
                       'expected': current.get('body'), 'proposed': body, 'watermark': snapshot['watermark'],
                      'plan': 'lead-owned: request proof/nudge only; never infer ticked steps'}
            p = snapshot['projects'].get(project_id)
            # Waiting todo intent requires chief-authenticated attribution, not
            # a lead claiming that a principal question has already been asked.
            intent['todo_intent'] = ({'owner_marker': f'chief-desk-wait:{project_id}',
                                      'body': p['your_part'], 'reference': p['decision_ref']}
                                     if p and p.get('decision_ref') and p['your_part'] else None)
            intent['todo_status'] = 'native proof required; never edit unrelated todos'
            intent['todo_ownership'] = 'only returned ids reconciled to this exact project/marker; no edits inferred from title'
            intent['todo_delivery'] = 'pending adapter proof; list before create, uncertain means reconcile, never blind retry'
            self.set_meta('knowledge:' + project_id, encoded(intent))
            return {**intent, 'send': False, 'reason': 'staged adapter intent only; native proof pending'}

    def knowledge_result(self, project_id, intent_id, state, note_id=None, body=None):
        """Record later native list/save evidence; caller is trusted adapter/operator.

        The uncertain path is reconciled by list/ownership/body evidence, never by
        issuing another create. A late successful result keeps its id and marks
        latest data pending instead of losing the id and duplicating the note.
        Future integration must check managed schemaVersion/ok/action/data, not
        assume HTTP status shapes. Supply actual saved/listed body from native
        evidence, never an echo of the submitted proposal; errors are not success.
        Native scope/ownership validation and persistence remain adapter obligations.
        """
        with guard(self.home):
            current = self.knowledge_state(project_id)
            if current.get('intent') != intent_id or current['state'] not in ('planned', 'uncertain', 'conflict'):
                raise ValueError('knowledge intent conflict')
            if state in ('uncertain', 'conflict'):
                current.update(state=state)
            elif state == 'applied':
                if not isinstance(note_id, str) or not note_id or body != current['proposed']:
                    raise ValueError('owned note id and exact saved body evidence required')
                current.update(state='applied', note_id=note_id, body=body,
                               pending_latest=current['watermark'] != self.watermark())
            else:
                raise ValueError('invalid knowledge result')
            self.set_meta('knowledge:' + project_id, encoded(current))
            return current

    def canvas_result(self, view_id, expected_revision, new_revision, watermark):
        """Record a real tool result later; never call Canvas or accept viewer URLs."""
        if str(UUID(view_id)) != view_id.lower() or type(new_revision) is not int:
            raise ValueError('invalid Canvas result')
        with guard(self.home):
            p = self.projection()
            if p['view_id'] not in (None, view_id) or p['revision'] != expected_revision:
                raise ValueError('Canvas revision conflict; read latest, do not overwrite')
            if (new_revision != (expected_revision or 0) + 1 or watermark != self.watermark()
                    or p.get('cache_watermark') != watermark):
                raise ValueError('old render or revision does not cover latest data')
            p.update(view_id=view_id, revision=new_revision, canvas_watermark=watermark, canvas_pending=False)
            atomic(self.root / 'projection.json', encoded(p) + '\n')

    def brief_patch(self, project_id, expected_revision, expected_row, cells):
        """Desk Projects-only cooperative update. Conflict is retained, never guessed."""
        project = self.project(project_id)
        request = {'project': project_id, 'expected_revision': expected_revision,
                   'before': expected_row, 'after': cells, 'watermark': self.watermark()}
        self.set_meta('brief_pending', encoded(request))
        with guard(self.home):
            require_protocol(self.home)
            path = self.home / 'brief.md'
            DestinationRoot(self.home).validate_all([path])
            text = path.read_text()
            if revision(text) != expected_revision:
                raise ValueError('brief revision conflict; pending patch retained')
            a, b = section(text, 'Projects')
            lines = text[a:b].splitlines(keepends=True)
            table = [line for line in lines if line.lstrip().startswith('|')]
            def columns(line):
                return [c.strip() for c in line.strip().strip('|').split('|')]
            if len(table) < 2 or columns(table[0]) != ['project', 'lead', 'where it stands', 'next', 'log']:
                raise ValueError('malformed Projects header')
            matches = [line for line in table[2:] if project['log'] in columns(line)]
            if len(matches) != 1 or len(columns(matches[0])) != 5 or matches[0] != expected_row:
                raise ValueError('duplicate/malformed/changed project row; reconciliation required')
            if len(cells) != 5 or cells[4] != project['log'] or any(not isinstance(c, str) or any(x in c for x in ('|', '\n', '\r')) for c in cells):
                raise ValueError('invalid Projects replacement')
            after = '| ' + ' | '.join(cells) + ' |\n'
            self.set_meta('brief_audit', encoded({**request, 'after_row': after, 'status': 'prepared'}))
            replacement = ''.join(after if line == expected_row else line for line in lines)
            atomic(path, text[:a] + replacement + text[b:])
            self.set_meta('brief_audit', encoded({**request, 'after_row': after, 'revision': revision(path.read_text()), 'status': 'completed'}))
            self.set_meta('brief_pending', '')

    def decision_update(self, project_id, expected_seq, your_part, decision_ref):
        """Trusted chief/operator trigger, not a claimed approval in lead text.

        Native adapter must authenticate chief before invoking this administration
        method. Expected source seq prevents a late answer clearing a newer wait.
        """
        # Persist decision separately, leaving lead source revision/age untouched.
        with guard(self.home), self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.registry = json.loads((self.root / 'registry.json').read_text())
            self.project(project_id)
            project = self._snapshot()['projects'].get(project_id)
            if not project or project['seq'] != expected_seq or not decision_ref:
                raise ValueError('late/wrong-project decision update')
            if your_part is not None and not isinstance(your_part, str):
                raise ValueError('invalid chief waiting update')
            payload = encoded({'source_seq': expected_seq, 'your_part': your_part, 'reference': decision_ref, 'received': now()})
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',
                            ('decision:' + project_id, payload))
            self.db.execute('INSERT INTO changes(kind,created,payload) VALUES(?,?,?)', ('chief-decision:' + project_id, now(), payload))
            self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('generation', str(self.watermark() + 1)))
        return self.project_files()


def render_view(snapshot):
    local = Path(__file__).with_name('progress.template.html')
    template = (local if local.exists() else Path(__file__).resolve().parent.parent / 'kits/chief/desk/progress.template.html').read_text()
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for name, p in sorted(snapshot['projects'].items(), key=lambda item: (not bool(item[1]['your_part']), item[0])):
        age = 'Older source' if timestamp(snapshot['assembled']) - timestamp(p['observed']) > 86400 else 'Reported snapshot'
        part = p['your_part'] if p['your_part'] else 'Unknown; no current request confirmed'
        if p['your_part'] and not p.get('decision_ref'):
            part = 'With chief (not confirmed asked): ' + part
        cards.append(f'''<article><header><h2>{esc(name)}</h2><span>{esc(p['state'])} · {age}</span></header>
<dl><dt>Landed</dt><dd>{esc(p['landed'])}</dd><dt>Next</dt><dd>{esc(p['next'])}</dd><dt>Your part</dt><dd>{esc(part)}</dd></dl>
<p class="meta">Observed {esc(p['observed'])} · received {esc(p['received'])} · lead report {esc(p['id'])} · {esc(p['action'])}</p>
<details><summary>Record &amp; desk reply</summary><div class="audit">{esc(p['answer'])}<br>Evidence: {esc(encoded(p['evidence']))}<br>Source revision {p['source_revision']} · receipt {p['seq']}</div></details></article>''')
    for name in snapshot.get('missing', []):
        cards.append(f'<article><header><h2>{esc(name)}</h2><span>Missing verified report</span></header><dl><dt>Landed</dt><dd>Unknown</dd><dt>Next</dt><dd>Unknown</dd><dt>Your part</dt><dd>Unknown; check the last record with chief.</dd></dl></article>')
    return template.replace('@@CARDS@@', ''.join(cards) or '<p>No verified project reports. Current progress unknown.</p>').replace('@@ASSEMBLED@@', esc(snapshot['assembled'])).replace('@@WATERMARK@@', str(snapshot['watermark'])).replace('@@QUARANTINED@@', str(snapshot['quarantined'])).replace('@@BRIEF@@', 'pending reconciliation' if snapshot.get('brief_pending') else 'not checked by this render')


def resolve_route(home, project_id, lead):
    """Read-only routing plan, not liveness proof or send. Invalid opt-in fails closed."""
    home = Path(home)
    paths = [home / 'desk/routes.json', home / 'desk.json', home / 'chief.json']
    DestinationRoot(home).validate_all(paths)
    routes = json.loads(paths[0].read_text()) if paths[0].exists() else {'projects': {}}
    route = routes.get('projects', {}).get(ident(project_id))
    if route and route.get('enabled'):
        if lead not in route['leads'] or type(route['epoch']) is not int or route['epoch'] < 1:
            raise ValueError('route adoption identity/epoch mismatch')
        pointer = paths[1]
    else:
        pointer = paths[2]
    data = json.loads(pointer.read_text())
    if not re.fullmatch(r'ses_[A-Za-z0-9]+', data.get('session', '')) or data.get('directory') != str(home):
        raise ValueError('route unavailable; no silent fallback')
    timestamp(data.get('updated'))  # rotation, not heartbeat
    return {**data, 'pointer': str(pointer), 'epoch': route['epoch'] if route and route.get('enabled') else 0,
            'adoption_proven': False, 'liveness_proven': False}
