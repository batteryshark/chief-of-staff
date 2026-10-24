"""Promo-only local estimates. No provider balance, transport, or credential access."""
import copy
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

def validate_policy(value):
    if (not isinstance(value, dict) or set(value) != {'grant_micro_usd', 'renewal_day'}
            or type(value['grant_micro_usd']) is not int or value['grant_micro_usd'] <= 0
            or value['grant_micro_usd'] > 1_000_000_000_000
            or type(value['renewal_day']) is not int or not 1 <= value['renewal_day'] <= 28):
        raise ValueError('promo policy requires positive integer grant_micro_usd and renewal_day 1..28')
    return dict(value)


def load_policy(path):
    from pathlib import Path
    try:
        return validate_policy(json.loads(Path(path).read_text()))
    except (OSError, ValueError):
        raise ValueError('promo policy missing/invalid; configure local promo-policy.json before installation/use') from None
ROUTES = {
    'api-fable': {'model': 'anthropic-promo/claude-fable-5-1', 'variant': 'high',
                  'purpose': 'independent-review'},
    'api-opus': {'model': 'anthropic-promo/claude-opus-5-5',
                 'purpose': 'api-only'},
    'api-haiku-proof': {'model': 'anthropic-promo/claude-haiku-5-5', 'purpose': 'proof'},
}
RESERVES = {'api-fable': 17_000_000, 'api-opus': 6_000_000, 'api-haiku-proof': 1_000_000}
# Official first-party global standard prices, USD / million tokens, 2026-10-23.
# Cache creation uses the higher 1h rate when native usage does not distinguish TTL.
RATES = {'claude-fable-5-1': (10, 50, 20, .25),
         'claude-opus-5-5': (4, 20, 8, .20),
         'claude-haiku-5-5': (.50, 2.50, 1, .05)}  # conservative long-context tier


def cycle(now, renewal_day):
    """UTC accounting convention only; not a claim about provider grant timing."""
    d = datetime.fromtimestamp(now, timezone.utc)
    start = d.replace(day=renewal_day, hour=0, minute=0, second=0, microsecond=0)
    if d < start:
        y, m = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
        start = start.replace(year=y, month=m)
    y, m = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    end = start.replace(year=y, month=m)
    return start.isoformat(), end.timestamp()


def plan(task):
    route = ROUTES.get(task.get('route'))
    if not route or task.get('purpose') != route['purpose']:
        raise ValueError('promo requires explicit api-fable independent-review or api-opus api-only purpose')
    if any(task.get(k) for k in ('goal', 'tools', 'warming', 'continue_session')):
        raise ValueError('promo supports fresh bounded single-turn no-tools jobs only')
    text = task.get('text')
    if not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 32768:
        raise ValueError('promo requires nonempty text at most 32768 UTF-8 bytes')
    if route['purpose'] == 'proof' and text != 'Reply OK only.':
        raise ValueError('Haiku proof permits only the approved tiny prompt')
    return {'selected': {'route': task['route'], **route}, 'dispatch_allowed': False,
            'reason': 'prepare reserves credit before dispatch', 'subscription_fallback': False,
            'reserve_micro_usd': RESERVES[task['route']]}


def absent_only(existing, additions):
    """Pure scoped merge; collisions abort, even equal values. Never prints input."""
    out = copy.deepcopy(existing)
    for group in ('providers', 'agents'):
        entries = additions.get(group, {})
        if not isinstance(out.get(group, {}), dict):
            raise ValueError('configuration group is not an object')
        if set(entries) & set(out.get(group, {})):
            raise ValueError('scoped config entry already exists; parent review required')
        out.setdefault(group, {}).update(copy.deepcopy(entries))
    return out


def usage_cost(model, tokens):
    """Local price estimate: native input excludes cache; output excludes reasoning."""
    rates = RATES[model]
    cache = tokens.get('cache', {})
    values = [tokens.get('input'), tokens.get('output'), cache.get('write'), cache.get('read'),
              tokens.get('reasoning')]
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError('unknown token usage; retain full liability')
    values = [values[0], values[1] + values[4], values[2], values[3]]
    from decimal import Decimal, ROUND_CEILING
    return int(sum(Decimal(v) * Decimal(str(r)) for v, r in zip(values, rates))
               .to_integral_value(rounding=ROUND_CEILING))


class Credit:
    """Separate durable counter; BEGIN IMMEDIATE serializes concurrent admission.

    Internal reservation primitive only. Not proof that native dispatch obeys a bound.
    Unknown liabilities survive rollover; cycles must be explicitly verified by parent.
    """
    def __init__(self, path, policy=None):
        from pathlib import Path
        self.policy = validate_policy(policy) if policy is not None else load_policy(Path(path).parent / 'promo-policy.json')
        self.grant = self.policy['grant_micro_usd']
        self.stop = self.grant * 9 // 10
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        os.chmod(path, 0o600)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS cycles (id TEXT PRIMARY KEY, baseline INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS holds (id TEXT PRIMARY KEY, cycle TEXT NOT NULL,
            bound INTEGER NOT NULL, actual INTEGER, receipt TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS authority (cycle TEXT PRIMARY KEY, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, session TEXT UNIQUE, body TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def verify_cycle(self, cid, baseline):
        # No automatic assertion of a fresh provider grant or zero outside consumption.
        if type(baseline) is not int or not 0 <= baseline <= self.grant:
            raise ValueError('invalid known starting promo consumption')
        self.db.execute('INSERT INTO cycles VALUES (?, ?)', (cid, baseline))

    def status(self, now):
        cid, expiry = cycle(now, self.policy['renewal_day'])
        row = self.db.execute('SELECT baseline FROM cycles WHERE id=?', (cid,)).fetchone()
        spent = (row[0] if row else 0) + self.db.execute(
            'SELECT coalesce(sum(actual),0) FROM holds WHERE cycle=?', (cid,)).fetchone()[0]
        held = self.db.execute('SELECT coalesce(sum(bound),0) FROM holds WHERE actual IS NULL').fetchone()[0]
        return {'label': 'promo', 'kind': 'local estimate, NOT provider balance',
                'grant_usd': self.grant / 1e6, 'spent_usd': spent / 1e6 if row else None,
                'held_usd': held / 1e6, 'remaining_usd': max(0, self.grant-spent-held)/1e6 if row else None,
                'stop_usd': self.stop / 1e6, 'expiry': datetime.fromtimestamp(expiry, timezone.utc).date().isoformat() if row else None,
                'accounting_cycle_end_utc': datetime.fromtimestamp(expiry, timezone.utc).isoformat(),
                'provider_expiry_time_verified': False,
                'burn': 0 < expiry-now <= 3*86400, 'days_to_renewal': (expiry-now)/86400,
                'cycle_verified': bool(row), 'cycle': cid,
                'bound_breached': bool(self.db.execute(
                    'SELECT 1 FROM holds WHERE actual>bound LIMIT 1').fetchone())}

    def reserve(self, aid, bound, now, job=None):
        limit = RESERVES['api-fable'] if job and job.get('route') == 'api-fable' else 20_000_000
        if type(bound) is not int or not 0 < bound <= limit:
            raise ValueError('liability must be positive and within the route admission limit')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if job is not None:
                self.require_authority(now)
            s = self.status(now)
            if s['bound_breached']:
                raise ValueError('prior liability bound exceeded; parent reconciliation required')
            if not s['cycle_verified']:
                raise ValueError('cycle grant/starting consumption unverified')
            if self.db.execute('SELECT 1 FROM holds WHERE id=?', (aid,)).fetchone():
                raise ValueError('reservation id already used; never redispatch it')
            # Both settled and all unresolved liabilities count against the local 90% threshold.
            used = self.db.execute('SELECT baseline FROM cycles WHERE id=?', (s['cycle'],)).fetchone()[0]
            used += self.db.execute('SELECT coalesce(sum(actual),0) FROM holds WHERE cycle=?',
                                    (s['cycle'],)).fetchone()[0]
            used += self.db.execute('SELECT coalesce(sum(bound),0) FROM holds WHERE actual IS NULL').fetchone()[0]
            if used + bound > self.stop:
                raise ValueError(f'promo ${self.stop / 1e6:g} stop; BURN/prefer cannot waive it')
            self.db.execute('INSERT INTO holds VALUES (?, ?, ?, NULL, NULL)', (aid, s['cycle'], bound))
            if job is not None:
                self.db.execute('INSERT INTO jobs VALUES (?,NULL,?)', (aid, json.dumps(job)))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def settle(self, aid, receipt, actual):
        if type(actual) is not int or actual < 0 or not receipt:
            raise ValueError('unknown usage; retain liability')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT bound,actual,receipt FROM holds WHERE id=?', (aid,)).fetchone()
            if row is None:
                raise ValueError('unknown reservation')
            if row[1] is not None:
                if (row[1], row[2]) != (actual, receipt):
                    raise ValueError('conflicting settlement')
            else:
                self.db.execute('UPDATE holds SET actual=?,receipt=? WHERE id=?', (actual, receipt, aid))
            self.db.execute('COMMIT')
            return {'bound_exceeded': actual > row[0]}
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def settle_native(self, aid, message, expected_model):
        """Account a clean native assistant receipt; caller must reconcile all requests.

        Does not certify absence of hidden/auxiliary traffic. Errors/retries retain holds.
        """
        ref = message.get('model', {})
        if (message.get('type') != 'assistant' or message.get('finish') not in ('stop', 'length')
                or message.get('error') or message.get('retry')
                or not message.get('time', {}).get('completed')
                or ref.get('providerID') != 'anthropic-promo' or ref.get('id') != expected_model
                or not message.get('id')):
            raise ValueError('incomplete/unknown native liability; retain reservation')
        return self.settle(aid, message['id'], usage_cost(expected_model, message.get('tokens', {})))

    def authorize(self, now, approval, baseline=0):
        if (approval.get('console_backstop') is not True or approval.get('exclusive_key') is not True
                or not isinstance(approval.get('reference'), str) or not approval['reference']
                or approval.get('verified_cycle') != cycle(now, self.policy['renewal_day'])[0]):
            raise ValueError('verified current-cycle Console backstop and exclusive-key authority required')
        # Called only by parent-authorized installer/cycle verification. No account effects.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.verify_cycle(cycle(now, self.policy['renewal_day'])[0], baseline)
            self.db.execute('INSERT INTO authority VALUES (?,?)', (cycle(now, self.policy['renewal_day'])[0], json.dumps({**approval, 'policy': self.policy})))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def require_authority(self, now):
        row = self.db.execute('SELECT body FROM authority WHERE cycle=?', (cycle(now, self.policy['renewal_day'])[0],)).fetchone()
        if not row:
            raise ValueError('current-cycle Console backstop approval required; renewal unverified')
        a = json.loads(row[0])
        if a.get('policy') != self.policy or a.get('console_backstop') is not True or a.get('exclusive_key') is not True:
            raise ValueError('Console backstop approval required')

    def prepare(self, task, now):
        p = plan(task)
        self.require_authority(now)
        from pathlib import Path
        directory = str(Path(task['directory']).expanduser().resolve(strict=True))
        if not Path(directory).is_dir():
            raise ValueError('directory required')
        aid = task.get('attempt')
        if not isinstance(aid, str) or not aid or len(aid) > 120:
            raise ValueError('unique caller attempt id required')
        job = {'route': task['route'], 'model': p['selected']['model'].split('/')[1],
               'variant': p['selected'].get('variant'), 'directory': directory,
               'digest': digest(task['text']), 'state': 'prepared', 'created_at': now}
        self.reserve(aid, p['reserve_micro_usd'], now, job)
        from .promo_native import create_body
        return {'attempt': aid, 'dispatch_allowed': True, 'selected': p['selected'],
                'reserve_micro_usd': p['reserve_micro_usd'],
                'next_action': 'promo-dispatch', 'subscription_fallback': False,
                'native_create': {'method': 'post', 'path': '/api/session',
                                  'body': create_body(job, aid)}}

    def job(self, aid):
        row = self.db.execute('SELECT body FROM jobs WHERE id=?', (aid,)).fetchone()
        if not row:
            raise ValueError('unknown promo attempt')
        return json.loads(row[0])

    def cancel_unsent(self, aid, confirmed_not_sent):
        """Administrative release, never a provider receipt. Serialize with create."""
        if confirmed_not_sent is not True:
            raise ValueError('explicit confirmed_not_sent=true required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute(
                'SELECT j.session,j.body,h.actual,h.receipt FROM jobs j JOIN holds h ON h.id=j.id WHERE j.id=?',
                (aid,)).fetchone()
            if row is None:
                raise ValueError('unknown promo attempt/hold')
            job = json.loads(row[1])
            if (row[0] is not None or 'session' in job or job.get('state') != 'prepared'
                    or row[2] is not None or row[3] is not None
                    or set(job) - {'route', 'model', 'variant', 'directory', 'digest', 'state', 'created_at'}):
                raise ValueError('only pristine prepared unbound unsettled attempts may cancel')
            job.update(state='cancelled', administrative_release={
                'kind': 'confirmed-unsent', 'confirmed_not_sent': True,
                'provider_usage_claimed': False})
            # Zero is the accounting release sentinel; receipt deliberately stays NULL.
            self.db.execute('UPDATE holds SET actual=0 WHERE id=?', (aid,))
            self.db.execute('UPDATE jobs SET body=? WHERE id=?', (json.dumps(job), aid))
            self.db.execute('COMMIT')
            return {'attempt': aid, 'state': 'cancelled', 'administrative_release': True,
                    'provider_usage_claimed': False}
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def change(self, aid, expected, state, **fields):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            job = self.job(aid)
            if job['state'] != expected:
                raise ValueError('attempt state forbids duplicate send/bind; retain hold and collect')
            job.update(fields, state=state)
            self.db.execute('UPDATE jobs SET session=?,body=? WHERE id=?',
                            (job.get('session'), json.dumps(job), aid))
            self.db.execute('COMMIT')
            return job
        except BaseException:
            self.db.execute('ROLLBACK')
            raise


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def credit_line(s):
    return (f"CREDIT promo | grant ${s['grant_usd']:g} | spent {s['spent_usd']} | held {s['held_usd']} | "
            f"remaining {s['remaining_usd']} USD | expiry {s['expiry']} | "
            f"{'BURN' if s['burn'] else 'HOLD'} ~{s['days_to_renewal']:.1f} accounting days | "
            'local estimate, not provider balance; unverified cycles block admission')
