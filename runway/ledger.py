"""Transactional admissions. A lost dispatch response never releases capacity by timeout."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .policy import decide, instant, live_windows, timestamp, validate
from .usage import assess

ACTIVE = ('admitted', 'running', 'uncertain')


class Ledger:
    def __init__(self, path):
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        os.chmod(path, 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS preferences (scope TEXT PRIMARY KEY, body TEXT NOT NULL)')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')

    def close(self):
        self.db.close()

    def attempts(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM attempts ORDER BY rowid')]

    def get(self, aid):
        row = self.db.execute('SELECT body FROM attempts WHERE id=?', (aid,)).fetchone()
        if not row:
            raise ValueError('unknown attempt')
        return json.loads(row[0])

    def save(self, attempt):
        self.db.execute('INSERT OR REPLACE INTO attempts VALUES (?, ?)',
                        (attempt['id'], json.dumps(attempt, allow_nan=False)))

    def preference(self, scope):
        row = self.db.execute('SELECT body FROM preferences WHERE scope=?', (scope,)).fetchone()
        return json.loads(row[0]) if row else None

    def prefer(self, config, snapshot, scope, route_id, window_id, now):
        validate(config)
        if snapshot.get('schema_version') != 2 or snapshot.get('passive') is not True:
            raise ValueError('Tarmac passive snapshot v2 is required')
        if not scope:
            raise ValueError('a preference requires an explicit project/session scope')
        routes = [r for r in config['routes'] if r['id'] == route_id]
        if len(routes) != 1:
            raise ValueError('unknown route')
        source, _, windows = live_windows(snapshot, routes[0], now)
        w = next((w for w in windows if w['id'] == window_id), None)
        if not w or instant(w.get('resets_at')) is None:
            raise ValueError('use-before-reset requires a known, future reset for this route')
        p = {'scope': scope, 'source_id': source['id'], 'window_id': window_id,
             'reset_at': w['resets_at'], 'expires_at': w['resets_at'], 'created_at': timestamp(now),
             'mode': 'use-before-reset', 'route': route_id}
        self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?, ?)', (scope, json.dumps(p)))
        return p

    def clear_preference(self, scope):
        self.db.execute('DELETE FROM preferences WHERE scope=?', (scope,))

    def plan(self, config, snapshot, catalog, task, now, *, admit=False):
        # Lock spans decision + insertion so competing chiefs cannot double-admit.
        with self.transaction():
            attempts = self.attempts()
            same_job = [a for a in attempts if a['scope'] == task['scope'] and a['job'] == task['job']]
            previous = same_job[-1] if same_job else None
            if previous and previous['task']['directory'] != task['directory']:
                raise ValueError('continuation must retain the original directory/worktree')
            if previous and previous['state'] in ACTIVE:
                return {'dispatch_allowed': False, 'attempt': previous,
                        'reason': 'This job is already admitted; reconcile its session before retrying'}
            if previous and previous['state'] in ('completed', 'cancelled'):
                raise ValueError('this job is terminal; new authorized work needs a new job id')
            if task.get('writer', True):
                conflict = next((a for a in attempts if a['state'] in ACTIVE and
                                 a['task'].get('writer', True) and
                                 a['task']['directory'] == task['directory']), None)
                if conflict:
                    return {'dispatch_allowed': False, 'reason': 'Another writer owns this directory',
                            'attempt_id': conflict['id']}
            # Usage is read at dispatch time: burnable allowances are preferred automatically.
            usage = assess(config, snapshot, now, config.get('burn'))
            result = decide(config, snapshot, catalog, task, attempts, self.preference(task['scope']), now,
                            {b['source'] for b in usage['burn']})
            result['usage'] = {'burn': usage['burn'], 'low': usage['low']}
            result['dispatch_allowed'] = False
            if not admit or not result['selected']:
                return result
            choice = result['selected']
            aid = uuid.uuid4().hex
            attempt = {**choice, 'id': aid, 'scope': task['scope'], 'job': task['job'],
                       'state': 'admitted', 'task': task, 'created_at': timestamp(now),
                       'message_id': 'msg_runway' + aid, 'policy_version': 1,
                       'session_id': previous.get('session_id') if previous else None,
                       'checkpoint': previous.get('checkpoint') if previous else None}
            self.save(attempt)
            args = {'model': choice['model'], 'directory': task['directory'],
                    'returnResult': True, 'messageId': attempt['message_id']}
            for field in ('variant', 'agent'):
                if choice.get(field):
                    args[field] = choice[field]
            if attempt['session_id']:
                args['sessionId'] = attempt['session_id']
            else:
                args['title'] = task['job'][:80]
            result.update(dispatch_allowed=True, attempt=attempt,
                          action='session.send' if attempt['session_id'] else 'session.create', args=args)
            return result

    def bind(self, aid, session, now):
        with self.transaction():
            a = self.get(aid)
            if a['state'] not in ACTIVE:
                raise ValueError('only an active admission can bind a session')
            sid = session['id']
            if a.get('session_id') and a['session_id'] != sid:
                raise ValueError('continuation must retain its existing session')
            if session.get('location', {}).get('directory') != a['task']['directory']:
                raise ValueError('worker directory differs from the reserved directory')
            ref = session.get('model') or {}
            if f"{ref.get('providerID')}/{ref.get('id')}" != a['model'] or (ref.get('variant') or 'default') != (a.get('variant') or 'default'):
                raise ValueError('worker model/variant differs from the admitted route')
            if any(b['id'] != aid and b.get('session_id') == sid and b['state'] in ACTIVE for b in self.attempts()):
                raise ValueError('session already belongs to another active attempt')
            a.update(session_id=sid, state='running', bound_at=timestamp(now))
            self.save(a)
            return a

    def finish(self, aid, state, checkpoint, evidence, now):
        if state not in ('completed', 'quiescent', 'cancelled', 'unsent', 'uncertain'):
            raise ValueError('invalid final state')
        with self.transaction():
            a = self.get(aid)
            if a['state'] not in ACTIVE:
                raise ValueError('attempt has already ended')
            if state == 'uncertain':
                a.update(state=state, evidence=evidence)
            elif state == 'unsent':
                if a.get('session_id') or evidence.get('confirmed_not_sent') is not True:
                    raise ValueError('unsent requires confirmed non-delivery and no bound session')
                a.update(state=state, finished_at=timestamp(now), evidence=evidence)
            else:
                if not a.get('session_id') or evidence.get('session_id') != a['session_id']:
                    raise ValueError('verified bound session is required')
                if evidence.get('idle') is not True or evidence.get('inbox_empty') is not True:
                    raise ValueError('worker must be idle with no queued work before releasing admission')
                if evidence.get('tools_reconciled') is not True or evidence.get('effects_reconciled') is not True:
                    raise ValueError('reconcile pending tools and external side effects first')
                if state in ('completed', 'quiescent') and (instant(evidence.get('last_idle_at')) is None or
                        instant(evidence['last_idle_at']) < instant(a['created_at'])):
                    raise ValueError('no terminal execution observed since this admission')
                if state == 'completed' and evidence.get('outcome') != 'succeeded':
                    raise ValueError('completion requires a successful terminal execution')
                if state == 'quiescent':
                    for key in ('objective', 'directory', 'changes', 'tests', 'next', 'side_effects'):
                        if not isinstance(checkpoint.get(key), str) or not checkpoint[key].strip():
                            raise ValueError(f'checkpoint requires {key}')
                    if checkpoint['directory'] != a['task']['directory']:
                        raise ValueError('checkpoint directory must retain the worktree')
                a.update(state=state, checkpoint=checkpoint, evidence=evidence, finished_at=timestamp(now))
            self.save(a)
            return a
