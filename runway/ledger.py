"""Transactional admissions. A lost dispatch response never releases capacity by timeout."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .policy import decide, instant, live_windows, timestamp, validate, validate_exclusions
from .usage import assess
from .failure import quota_failure
from .checkout import checkout_identity, revalidate_checkout, source_directory

ACTIVE = ('admitted', 'running', 'uncertain')


class Ledger:
    def __init__(self, path):
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        os.chmod(path, 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS preferences (scope TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS cooldowns (attempt TEXT, failure_key TEXT, body TEXT NOT NULL, PRIMARY KEY (attempt, failure_key))')

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

    def cooldowns(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM cooldowns')]

    def report_failure(self, aid, failure, now):
        with self.transaction():
            a = self.get(aid)
            if not a.get('session_id') or not a.get('bound_at'):
                raise ValueError('provider failure requires a dispatched, bound attempt')
            c = quota_failure(failure, now)
            if c is None:
                return {'recorded': False, 'reason': 'not a provider quota/rate-limit observation'}
            old = self.db.execute('SELECT body FROM cooldowns WHERE attempt=? AND failure_key=?', (aid, c['key'])).fetchone()
            if old:
                original = json.loads(old[0])
                if original['reset_basis'].startswith('bounded') and not c['reset_basis'].startswith('bounded'):
                    # Richer reset evidence may replace an unknown-reset fallback,
                    # but relative hints still anchor to the FIRST failure clock.
                    c = quota_failure({**failure, 'observed_at': original['observed_at']}, now)
                else:
                    return {'recorded': True, 'cooldown': original}
            if instant(c['observed_at']) < instant(a['created_at']):
                raise ValueError('failure predates the attempt')
            if any(b['id'] != aid and b.get('session_id') == a['session_id'] and
                   instant(a['created_at']) < instant(b['created_at']) <= instant(c['observed_at'])
                   for b in self.attempts()):
                raise ValueError('failure belongs to a newer attempt on this session')
            if a['state'] in ('quiescent', 'completed', 'cancelled', 'unsent') and a.get('finished_at') and instant(c['observed_at']) > instant(a['finished_at']):
                raise ValueError('failure postdates this ended/checkpointed attempt; use its actual attempt')
            c.update({k: a.get(k) for k in ('host', 'pool', 'model', 'route', 'source_id', 'provider', 'account')})
            c['attempt'] = aid
            # Re-reporting the same failure cannot slide a relative reset forward.
            self.db.execute('INSERT OR REPLACE INTO cooldowns VALUES (?, ?, ?)', (aid, c['key'], json.dumps(c)))
            saved = self.db.execute('SELECT body FROM cooldowns WHERE attempt=? AND failure_key=?', (aid, c['key'])).fetchone()
            return {'recorded': True, 'cooldown': json.loads(saved[0])}

    def plan(self, config, snapshot, catalog, task, now, *, admit=False, exclude_routes=None):
        validate_exclusions(config, [] if exclude_routes is None else exclude_routes)
        task = dict(task)
        identity = checkout_identity(task)
        # Lock spans decision + insertion so competing chiefs cannot double-admit.
        with self.transaction():
            attempts = self.attempts()
            same_job = [a for a in attempts if a['scope'] == task['scope'] and a['job'] == task['job']]
            previous = same_job[-1] if same_job else None
            if previous and previous['task']['directory'] != task['directory']:
                raise ValueError('continuation must retain the original session directory')
            if previous:
                if previous['task'].get('checkout') != task.get('checkout'):
                    raise ValueError('continuation must retain the original checkout')
                revalidate_checkout(previous)
            if previous and previous['state'] in ACTIVE:
                return {'dispatch_allowed': False, 'attempt': previous,
                        'reason': 'This job is already admitted; reconcile its session before retrying'}
            if previous and previous['state'] in ('completed', 'cancelled'):
                raise ValueError('this job is terminal; new authorized work needs a new job id')
            if task.get('writer', True):
                conflict = next((a for a in attempts if a['state'] in ACTIVE and
                                 a['task'].get('writer', True) and
                                 source_directory(a['task']) == source_directory(task)), None)
                if conflict:
                    return {'dispatch_allowed': False, 'reason': 'Another writer owns this directory',
                            'attempt_id': conflict['id']}
            # Usage is read at dispatch time: burnable allowances are preferred automatically.
            usage = assess(config, snapshot, now, config.get('burn'))
            result = decide(config, snapshot, catalog, task, attempts, self.preference(task['scope']), now,
                            {b['source'] for b in usage['burn']}, exclude_routes=exclude_routes, cooldowns=self.cooldowns())
            result['exclude_routes'] = exclude_routes or []
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
            attempt['exclude_routes'] = exclude_routes or []
            if identity is not None:
                attempt['checkout_identity'] = identity
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
            if a.get('host_dispatch') and a['host_dispatch']['state'] != 'collected':
                raise ValueError('incomplete native dispatch requires exact-input reconciliation, not bind')
            sid = session['id']
            if a.get('session_id') and a['session_id'] != sid:
                raise ValueError('continuation must retain its existing session')
            if session.get('location', {}).get('directory') != a['task']['directory']:
                raise ValueError('worker directory differs from the reserved directory')
            revalidate_checkout(a)
            ref = session.get('model') or {}
            if f"{ref.get('providerID')}/{ref.get('id')}" != a['model'] or (ref.get('variant') or 'default') != (a.get('variant') or 'default'):
                raise ValueError('worker model/variant differs from the admitted route')
            if any(b['id'] != aid and b.get('session_id') == sid and b['state'] in ACTIVE for b in self.attempts()):
                raise ValueError('session already belongs to another active attempt')
            a.pop('usage_released', None)
            a.update(session_id=sid, state='running', bound_at=timestamp(now))
            self.save(a)
            return a

    def finish(self, aid, state, checkpoint, evidence, now):
        if state not in ('completed', 'quiescent', 'cancelled', 'unsent', 'uncertain'):
            raise ValueError('invalid final state')
        with self.transaction():
            a = self.get(aid)
            if a['state'] not in ACTIVE + ('quiescent',):
                raise ValueError('attempt has already ended')
            if state in ('completed', 'quiescent') and a.get('host_dispatch') and a['host_dispatch']['state'] != 'collected':
                raise ValueError('uncollected native dispatch cannot be completed/checkpointed')
            if a['state'] == 'quiescent' and state == 'unsent':
                raise ValueError('a checkpointed worker cannot be unsent')
            if state != 'uncertain' and any(b['id'] != aid and a.get('session_id') and
                    b.get('session_id') == a['session_id'] and b['state'] in ACTIVE
                    for b in self.attempts()):
                raise ValueError('session belongs to a newer active attempt; retain the old checkpoint')
            if state == 'uncertain':
                # Quota release is not native-action admission or ownership release.
                # Only a real bind can reacquire a released hold, not a failed recheck.
                a['usage_released'] = (a.get('usage_released') is True or
                    a['state'] == 'quiescent' or bool(a.get('session_id') and
                    evidence.get('session_id') == a['session_id'] and
                    evidence.get('idle') is True and evidence.get('inbox_empty') is True and
                    instant(evidence.get('observed_at')) is not None and
                    instant(evidence['observed_at']) >= instant(a['created_at'])))
                a.update(state=state, evidence=evidence)
            elif state == 'unsent':
                if a.get('session_id') or evidence.get('confirmed_not_sent') is not True:
                    raise ValueError('unsent requires confirmed non-delivery and no bound session')
                a.update(state=state, finished_at=timestamp(now), evidence=evidence)
            else:
                # Terminal bookkeeping neither writes source nor resumes a worker.
                # Bind, continuation and checkpointing still validate the checkout.
                if state == 'quiescent':
                    revalidate_checkout(a)
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
                        raise ValueError('checkpoint directory must retain the session directory')
                    if checkpoint.get('checkout') != a['task'].get('checkout'):
                        raise ValueError('checkpoint must retain the source checkout')
                a.update(state=state, checkpoint=checkpoint or a.get('checkpoint'), evidence=evidence, finished_at=timestamp(now))
            self.save(a)
            return a

    def dispatch_get(self, aid):
        """Existing admission body only; no new queue/table or lifecycle."""
        return self.get(aid)

    def dispatch_save(self, aid, value, expected_state, now):
        with self.transaction():
            a = self.get(aid)
            if a['state'] not in ACTIVE:
                raise ValueError('dispatch requires an active admission')
            old = a.get('host_dispatch')
            if (old or {}).get('state') != expected_state:
                raise ValueError('dispatch CAS conflict; reconcile, never retry effects')
            transitions = {None: 'creating', 'creating': 'created', 'created': 'uncertain',
                           'uncertain': 'admitted', 'admitted': 'collected'}
            if expected_state not in transitions or value.get('state') != transitions[expected_state]:
                raise ValueError('invalid dispatch subrecord transition')
            if not old and (a.get('session_id') or a['state'] != 'admitted'):
                raise ValueError('fresh unbound admission required')
            ref = value.get('model') or {}
            if (value.get('id') != aid or value.get('inputID') != a['message_id'] or
                    value.get('directory') != a['task']['directory'] or
                    f"{ref.get('providerID')}/{ref.get('id')}" != a['model'] or
                    not a.get('variant') or ref.get('variant') != a['variant'] or
                    not value.get('agent') or a.get('agent') and value['agent'] != a['agent']):
                raise ValueError('dispatch differs from authorized admission selection')
            origin = value.get('origin') or {}
            if (not isinstance(origin.get('sessionID'), str) or not origin['sessionID'].startswith('ses_') or
                    not isinstance(origin.get('messageID'), str) or not origin['messageID'].startswith('msg_') or
                    not isinstance(origin.get('callID'), str) or not origin['callID'] or
                    origin.get('directory') != a['task']['directory']):
                raise ValueError('exact same-location native caller required')
            if old:
                for key in ('id', 'inputID', 'origin', 'model', 'agent', 'directory', 'text', 'textHash'):
                    if old.get(key) != value.get(key):
                        raise ValueError('immutable dispatch binding changed')
                if old.get('sessionID') and old['sessionID'] != value.get('sessionID'):
                    raise ValueError('worker ownership changed')
            revalidate_checkout(a)
            sid = value.get('sessionID')
            if value['state'] != 'creating':
                if not isinstance(sid, str) or not sid.startswith('ses_') or sid == origin['sessionID']:
                    raise ValueError('fresh distinct native worker required')
                if any(b['id'] != aid and b.get('session_id') == sid and b['state'] in ACTIVE
                       for b in self.attempts()):
                    raise ValueError('worker belongs to another admission')
                a['session_id'] = sid
            if value['state'] == 'collected':
                result = value.get('result') or {}
                if (result.get('origin') != origin or result.get('attemptID') != aid or
                        result.get('sessionID') != sid or result.get('inputID') != a['message_id'] or
                        result.get('model') != ref or not result.get('assistantID') or not result.get('idleID')):
                    raise ValueError('result does not belong to this exact input/caller')
            a['host_dispatch'] = value
            # Reuse existing uncertainty/running states; no timeout releases ownership.
            a['state'] = 'running' if value['state'] in ('admitted', 'collected') else 'uncertain'
            if value['state'] == 'admitted':
                a['bound_at'] = timestamp(now)
            self.save(a)
            return a

    def dispatch_incomplete(self, aid, input_id):
        with self.transaction():
            a = self.get(aid)
            d = a.get('host_dispatch') or {}
            if a['state'] not in ACTIVE or d.get('inputID') != input_id or d.get('state') != 'admitted':
                raise ValueError('only this admitted input can become incomplete')
            a['state'] = 'uncertain'
            d['incomplete'] = True
            a['host_dispatch'] = d
            self.save(a)
            return a
