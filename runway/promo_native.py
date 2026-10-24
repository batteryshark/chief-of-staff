"""Ordinary OpenCode CLI API calls. Inherited native auth; no auth/key inspection."""
import json
import re
import subprocess
import time
from urllib.parse import urlencode

from .promo import digest, usage_cost


class Native:
    def call(self, method, path, body=None):
        args = ['opencode', 'api', method, path]
        if body is not None:
            args += ['--data', json.dumps(body)]
        # No resend on timeout, nonzero exit or malformed output. Never relay stderr/body.
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=120, check=False)
            if r.returncode:
                raise ValueError('native API call failed; liability retained')
            return json.loads(r.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            raise ValueError('native API unavailable/unknown response; liability retained') from None

    def get(self, path):
        return self.call('get', path)


def session_path(sid):
    if not isinstance(sid, str) or not re.fullmatch(r'ses[a-zA-Z0-9_-]+', sid):
        raise ValueError('invalid native session id')
    return '/api/session/' + sid


def ref(job):
    r = {'providerID': 'anthropic-promo', 'id': job['model']}
    if job.get('variant'):
        r['variant'] = job['variant']
    return r


def same_model(actual, expected):
    """Only an omitted variant and the native literal 'default' are equivalent."""
    for model in (actual, expected):
        if (not isinstance(model, dict) or not {'id', 'providerID'} <= model.keys()
                or model.keys() - {'id', 'providerID', 'variant'}
                or any(not isinstance(model[k], str) or not model[k] for k in model)):
            return False
    return {**actual, 'variant': actual.get('variant', 'default')} == {
        **expected, 'variant': expected.get('variant', 'default')}


def validate_session(job, info):
    if (not same_model(info.get('model'), ref(job)) or info.get('agent') != 'api-promo-review'
            or info.get('location', {}).get('directory') != job['directory']
            or info.get('metadata', {}).get('promo_attempt') != job['attempt']):
        raise ValueError('session does not match reserved caller/route/location')


def create_body(job, aid):
    return {'title': 'API promo review', 'agent': 'api-promo-review', 'model': ref(job),
            'location': {'directory': job['directory']}, 'metadata': {'promo_attempt': aid}}


def bind(credit, aid, sid, native):
    job = {**credit.job(aid), 'attempt': aid}
    info = native.get(session_path(sid))['data']
    validate_session(job, info)
    messages = native.get(session_path(sid) + '/message?limit=1&order=asc')
    if messages['data'] or messages['cursor'].get('next'):
        raise ValueError('bind requires an empty fresh session')
    if job['state'] not in ('prepared', 'creating'):
        raise ValueError('attempt state forbids rebinding')
    credit.change(aid, job['state'], 'bound', session=sid)
    return {'attempt': aid, 'session': sid, 'state': 'bound'}


def dispatch(credit, aid, text, native, now=None):
    credit.require_authority(time.time() if now is None else now)
    job = credit.job(aid)
    if not isinstance(text, str) or digest(text) != job['digest']:
        raise ValueError('prompt differs from reserved input')
    # Durable claim precedes session creation. An uncertain result is never resent.
    job = credit.change(aid, 'prepared', 'creating')
    result = native.call('post', '/api/session', create_body(job, aid))
    sid = result['data']['id']
    bind(credit, aid, sid, native)
    return send(credit, aid, text, native, now)


def send(credit, aid, text, native, now=None):
    request = claim_send(credit, aid, text, native, now)
    native.call('post', request['native_prompt']['path'], request['native_prompt']['body'])
    return {k: v for k, v in request.items() if k != 'native_prompt'}


def claim_send(credit, aid, text, native, now=None):
    credit.require_authority(time.time() if now is None else now)
    job = credit.job(aid)
    if not isinstance(text, str) or digest(text) != job['digest']:
        raise ValueError('prompt differs from reserved input')
    path = session_path(job.get('session'))
    validate_session({**job, 'attempt': aid}, native.get(path)['data'])
    page = native.get(path + '/message?limit=1&order=asc')
    if page['data'] or page['cursor'].get('next'):
        raise ValueError('send requires empty fresh session')
    # Claim BEFORE the sole prompt call; crash/HTTP errors preserve this state and hold.
    credit.change(aid, 'bound', 'sent')
    return {'attempt': aid, 'session': job['session'], 'state': 'sent',
            'next_action': 'promo-settle', 'automatic_resend': False,
            'native_prompt': {'method': 'post', 'path': path + '/prompt',
                              'body': {'text': text, 'metadata': {'promo_attempt': aid}}}}


def collect(credit, aid, native):
    job = credit.job(aid)
    if job['state'] not in ('sent', 'settled'):
        raise ValueError('attempt not sent; unknown holds remain reserved')
    path = session_path(job['session'])
    info = native.get(path)['data']
    validate_session({**job, 'attempt': aid}, info)
    if job['session'] in native.get('/api/session/active')['data']:
        return {'attempt': aid, 'state': 'pending', 'held': True}
    for suffix in ('inbox', 'permission', 'form'):
        if native.get(path + '/' + suffix)['data']:
            return {'attempt': aid, 'state': 'pending', 'held': True}
    messages, cursor, seen = [], None, set()
    for _ in range(20):  # bounded receipt collection, never bounded inference by assertion
        query = {'limit': 100, 'order': 'asc'} if cursor is None else {'limit': 100, 'cursor': cursor}
        page = native.get(path + '/message?' + urlencode(query))
        for m in page['data']:
            if m['id'] in seen:
                raise ValueError('duplicate native receipt; retain liability')
            seen.add(m['id'])
            messages.append(m)
        cursor = page['cursor'].get('next')
        if not cursor:
            break
    else:
        raise ValueError('incomplete receipt pages; retain liability')
    users = [m for m in messages if m.get('type') == 'user']
    # The caller owns this one prompt; follow-on user/system work invalidates settlement.
    if (len(users) != 1 or users[0].get('metadata', {}).get('promo_attempt') != aid
            or digest(users[0].get('text', '')) != job['digest']
            or any(users[0].get(k) for k in ('files', 'agents', 'skills'))
            or any(m.get('type') in ('synthetic', 'compaction') for m in messages)):
        raise ValueError('unexpected caller/compaction traffic; retain liability')
    assistants = [m for m in messages if m.get('type') == 'assistant']
    if not assistants:
        return {'attempt': aid, 'state': 'pending', 'held': True}
    total, receipts = 0, []
    text = []
    for m in assistants:
        if (not same_model(m.get('model'), ref(job)) or m.get('agent') != 'api-promo-review'
                or m.get('finish') not in ('stop', 'length') or m.get('error') or m.get('retry')
                or not m.get('time', {}).get('completed')
                or any(c.get('type') == 'tool' for c in m.get('content', []))):
            raise ValueError('unknown/error/retry/tool liability retained')
        total += usage_cost(job['model'], m.get('tokens', {}))
        receipts.append({'id': m['id'], 'tokens': m['tokens']})
        text.extend(c.get('text', '') for c in m.get('content', []) if c.get('type') == 'text')
    # Settle observed caller-session usage only. Console backstop covers accepted
    # residual risk; do not claim title/auxiliary traffic is absent or provider balance.
    charged = total
    result = credit.settle(aid, digest(json.dumps(receipts, sort_keys=True)), charged)
    if job['state'] == 'sent':
        credit.change(aid, 'sent', 'settled', receipts=receipts, observed_micro_usd=total,
                      accounted_micro_usd=charged)
    return {'attempt': aid, 'session': job['session'], 'state': 'settled',
            'observed_micro_usd': total, 'accounted_micro_usd': charged,
            'accounting': 'local conservative estimate; native auxiliary usage not proven absent',
            'receipts': receipts, 'text': '\n'.join(text), **result}
