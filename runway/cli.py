"""One JSON request on stdin, one JSON result. Only reads native host APIs."""
import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .ledger import Ledger
from .policy import timestamp, validate, instant, validate_exclusions
from .usage import assess, burn_lines, table
from .checkout import checkout_identity


def registration():
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'opencode'
    records = []
    for path in state.glob('service*.json'):
        try:
            value = json.loads(path.read_text())
            if isinstance(value.get('url'), str):
                records.append(value)
        except (OSError, ValueError, TypeError):
            pass
    return records


class LocalAPI:
    def __init__(self, url, *, auth=False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') \
                or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('API address must be an HTTP loopback origin')
        self.url = url.rstrip('/')
        self.headers = {}
        if auth:
            password = os.environ.get('OPENCODE_SERVER_PASSWORD') or os.environ.get('OPENCODE_PASSWORD')
            if not password:
                matches = [r for r in registration() if r['url'].rstrip('/') == self.url]
                if len(matches) == 1:
                    password = matches[0].get('password')
            if password:
                user = os.environ.get('OPENCODE_SERVER_USERNAME') or os.environ.get('OPENCODE_USERNAME', 'opencode')
                self.headers['Authorization'] = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()

    def get(self, path, **query):
        # No proxy or redirect may forward local host credentials elsewhere.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **kw):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        url = self.url + path + ('?' + urllib.parse.urlencode(query) if query else '')
        with opener.open(urllib.request.Request(url, headers=self.headers), timeout=8) as response:
            return json.load(response)

    def catalog(self, directory, candidates=()):
        data = self.get('/api/model', **{'location[directory]': directory})
        # Location plugins may still be settling after the first catalog snapshot.
        for _ in range(5):
            if any(m.get('enabled') and (not candidates or f"{m.get('providerID')}/{m.get('id')}" in candidates) for m in data.get('data', [])):
                break
            time.sleep(0.2)
            data = self.get('/api/model', **{'location[directory]': directory})
        if str(Path(data.get('location', {}).get('directory', '')).resolve()) != directory:
            raise ValueError('host returned a catalog for another directory')
        return {'directory': directory, 'observed_at': timestamp(time.time()), 'models': data['data']}

    def session(self, sid):
        info = self.get('/api/session/' + urllib.parse.quote(sid, safe=''))['data']
        info['location']['directory'] = str(Path(info['location']['directory']).resolve())
        return info

    def idle_evidence(self, sid, expected_directory, *, quota_only=False):
        path = '/api/session/' + urllib.parse.quote(sid, safe='')
        info = self.session(sid)
        directory = info.get('location', {}).get('directory')
        if directory != expected_directory and not quota_only:
            raise ValueError('session moved; reconcile its worktree before releasing admission')
        active = self.get('/api/session/active')['data']
        pending = self.get(path + '/inbox')['data']
        permissions = self.get(path + '/permission')['data']
        forms = self.get(path + '/form')['data']
        # These are independent observations, not a native lock. Recheck immediately before sending.
        idle = info.get('time', {}).get('idle')
        idle_at = timestamp(idle / 1000) if isinstance(idle, (int, float)) else idle
        return {'last_idle_at': idle_at, 'session_id': sid, 'session_directory': directory,
                'directory_matches': directory == expected_directory,
                'idle': sid not in active, 'inbox_empty': not pending and not permissions and not forms,
                'outcome': info.get('outcome'), 'observed_at': timestamp(time.time())}

    def provider_failure(self, attempt):
        # V2 @opencode/client 2.0.23 SessionMessageAssistant.error, not tool errors,
        # transcript text, session outcome alone, or an HTTPError from this reader.
        data = self.get('/api/session/' + urllib.parse.quote(attempt['session_id'], safe='') +
                        '/message', limit=5, order='desc', type='assistant')['data']
        for message in data:
            ref = message.get('model') or {}
            at = message.get('time', {}).get('created')
            if (message.get('type') != 'assistant' or message.get('finish') != 'error' or
                    f"{ref.get('providerID')}/{ref.get('id')}" != attempt['model'] or
                    not isinstance(at, (int, float)) or at / 1000 < instant(attempt['created_at'])):
                continue
            error = message.get('error')
            if isinstance(error, dict) and isinstance(error.get('message'), str):
                at = message.get('time', {}).get('completed') or at
                # Structured provider response body is part of this assistant failure,
                # unlike arbitrary transcript/tool output. Bound it and never echo it.
                body = (error.get('response') or {}).get('body', '')
                text = error['message'][:4000] + ('\n' + body[:11999] if isinstance(body, str) else '')
                return {'message': text, 'status': error.get('status'),
                        'observed_at': timestamp(at / 1000), 'key': message['id'],
                        'provenance': 'native assistant.error'}
        return None


def handle(req, config, ledger, quota, host):
    action = req['action']
    # API-required work must never fall through to subscription/percent routing.
    if action in ('plan', 'prepare') and (req.get('task', {}).get('api_required') or
            req.get('task', {}).get('route') in ('api-fable', 'api-opus', 'api-haiku-proof')):
        from .promo import plan
        return plan(req['task'])
    if action == 'dispatch-get':
        return ledger.dispatch_get(req['attempt'])
    if action == 'dispatch-save':
        return ledger.dispatch_save(req['attempt'], req['value'], req['expected_state'], time.time())
    if action == 'dispatch-incomplete':
        return ledger.dispatch_incomplete(req['attempt'], req['input_id'])
    if action == 'status':
        if req.get('format') == 'json':
            return {'attempts': ledger.attempts(), 'preference': ledger.preference(req.get('scope', '')),
                    'cooldowns': ledger.cooldowns(),
                    'routes': config.get('routes', []), 'snapshot': quota.get('/api/v1/snapshot')}
        return Text(status_text(config, ledger, quota.get('/api/v1/snapshot'), req.get('scope', '')))
    if action == 'usage':
        # Read before dispatching new work: what would go unspent at its reset, and what is nearly gone.
        snapshot = quota.get('/api/v1/snapshot')
        if req.get('format') == 'json':
            result = assess(config, snapshot, time.time(), config.get('burn'))
            result.pop('choice', None)
            return result
        return Text(table(config, snapshot, time.time(), config.get('burn')))
    if action == 'clear-preference':
        ledger.clear_preference(req['scope'])
        return {'cleared': True}
    if action == 'prefer':
        if req.get('user_requested') is not True:
            raise ValueError('use-before-reset requires the user to request this preference')
        return ledger.prefer(config, quota.get('/api/v1/snapshot'), req['scope'],
                             req['route'], req['window'], time.time())
    if action in ('plan', 'prepare'):
        exclusions = req.get('exclude_routes', [])
        validate_exclusions(config, exclusions)
        task = dict(req['task'])
        task['directory'] = str(Path(task['directory']).expanduser().resolve(strict=True))
        checkout_identity(task)
        # Fetch both within this request; do not accept caller-supplied availability.
        snapshot = quota.get('/api/v1/snapshot')
        catalog = host.catalog(task['directory'], [r['model'] for r in config['routes']])
        if action == 'prepare':
            previous = [a for a in ledger.attempts() if a['scope'] == task['scope'] and a['job'] == task['job']]
            if previous and previous[-1]['state'] == 'quiescent':
                evidence = host.idle_evidence(previous[-1]['session_id'], task['directory'])
                if not evidence['idle'] or not evidence['inbox_empty']:
                    raise ValueError('continuation session became active or has queued work; reconcile it first')
        result = ledger.plan(config, snapshot, catalog, task, time.time(), admit=action == 'prepare', exclude_routes=exclusions)
        return result if req.get('format') == 'json' else compact_plan(result)
    if action == 'bind':
        return compact_attempt(ledger.bind(req['attempt'], host.session(req['session']), time.time()), req)
    if action == 'report-failure':
        if req.get('provider_failure') is not None:
            failure = dict(req['provider_failure'])
            failure['provenance'] = 'reported'
        else:
            a = ledger.get(req['attempt'])
            if not a.get('session_id') or not a.get('bound_at'):
                raise ValueError('provider failure requires a dispatched, bound attempt')
            if host is None:
                raise ValueError('native server required for automatic failure observation; or relay provider_failure')
            failure = host.provider_failure(a)
            if failure is None:
                return {'recorded': False, 'reason': 'no native provider failure in bounded assistant page; relay known error explicitly'}
        return ledger.report_failure(req['attempt'], failure, time.time())
    if action == 'finish':
        a = ledger.get(req['attempt'])
        observation = None
        if req.get('provider_failure') is not None:
            failure = dict(req['provider_failure'])
            failure['provenance'] = 'reported'
            observation = ledger.report_failure(a['id'], failure, time.time())
        elif a.get('session_id') and a.get('bound_at') and hasattr(host, 'provider_failure'):
            try:
                failure = host.provider_failure(a)
                if failure:
                    observation = ledger.report_failure(a['id'], failure, time.time())
            except (ValueError, OSError, KeyError, TypeError):
                observation = {'recorded': False, 'reason': 'native failure observation unavailable; use report-failure if known'}
        evidence = {key: req.get(key) for key in ('confirmed_not_sent', 'tools_reconciled', 'effects_reconciled')}
        if req['state'] != 'unsent' and a.get('session_id'):
            try:
                evidence.update(host.idle_evidence(a['session_id'], a['task']['directory'],
                                                  **({'quota_only': True} if req['state'] == 'uncertain' else {})))
            except (ValueError, OSError) as exc:
                if req['state'] != 'uncertain':
                    raise
                # Recording uncertainty must remain possible during native outages.
                # No verified idle evidence means no quota or ownership release.
                evidence['native_check'] = 'unavailable: ' + type(exc).__name__
        elif req['state'] not in ('unsent', 'uncertain'):
            if not a.get('session_id'):
                raise ValueError('bind the confirmed session before releasing this attempt')
        checkpoint = dict(req.get('checkpoint') or {})
        if checkpoint.get('directory'):
            checkpoint['directory'] = str(Path(checkpoint['directory']).expanduser().resolve())
        if checkpoint.get('checkout'):
            checkpoint['checkout'] = str(Path(checkpoint['checkout']).expanduser().resolve())
        result = compact_attempt(ledger.finish(req['attempt'], req['state'], checkpoint, evidence, time.time()), req)
        if observation:
            result = {**result, 'failure_observation': observation}
        return result
    raise ValueError('unknown action')


class Text(str):
    """A plain-text answer: printed as is, never wrapped in JSON."""


ACTIVE = ('admitted', 'running', 'uncertain', 'quiescent')


def status_text(config, ledger, snapshot, scope):
    lines = [table(config, snapshot, time.time(), config.get('burn'))]
    pref = ledger.preference(scope) if scope else None
    if pref:
        lines.append(f"Use-before-reset preference for {scope}: {pref.get('route', pref['source_id'])} "
                     f"until {pref['expires_at']}.")
    open_attempts = [a for a in ledger.attempts() if a['state'] in ACTIVE]
    lines.append(f'Open attempts: {len(open_attempts)}.')
    for a in open_attempts[-12:]:
        lines.append(f"- {a['job']} | {a['state']} | {a['route']} | session {a.get('session_id') or 'none'} | attempt {a['id']}"
                     f" | directory {a['task']['directory']}"
                     + (f" | checkout {a['task']['checkout']}" if 'checkout' in a['task'] else ''))
    for c in ledger.cooldowns():
        if instant(c['until']) > time.time():
            lines.append(f"Cooldown: {c['route']} | {c['model']} | {c['pool']} | until {c['until']} | {c['reason']} | {c['provenance']}")
    lines.append('Routes: ' + '; '.join(f"{r['id']}={r['model']}" + (f" {r['variant']}" if r.get('variant') else '')
                                         + f" [{','.join(r['categories'])}]" for r in config.get('routes', [])) + '.')
    return '\n'.join(lines)


def compact_attempt(a, req):
    if req.get('format') == 'json':
        return a
    keep = ('id', 'job', 'state', 'route', 'model', 'variant', 'session_id', 'message_id')
    result = {k: a.get(k) for k in keep if a.get(k) is not None}
    result.update({k: a['task'][k] for k in ('directory', 'checkout') if k in a['task']})
    return result


def compact_plan(result):
    """What an agent needs to dispatch: the choice, the exact args, and one line per alternative."""
    out = {'dispatch_allowed': result.get('dispatch_allowed', False)}
    sel = result.get('selected')
    if sel:
        out['selected'] = {k: sel.get(k) for k in ('route', 'model', 'variant', 'reason')}
    for key in ('action', 'args', 'reason', 'attempt_id', 'exclude_routes'):
        if result.get(key) is not None:
            out[key] = result[key]
    if result.get('attempt'):
        out['attempt'] = compact_attempt(result['attempt'], {})
        if result['attempt'].get('checkpoint'):
            out['attempt']['checkpoint'] = result['attempt']['checkpoint']
    if result.get('alternatives'):
        out['alternatives'] = [c['route'] for c in result['alternatives']]
    if result.get('rejected'):
        out['rejected'] = [f"{r['route']}: {r['reason']}" for r in result['rejected']]
    if result.get('usage'):
        out['usage'] = burn_lines(result['usage'])
    return out


def main():
    parser = argparse.ArgumentParser(description='Quota-aware chief-of-staff routing. Read routing/WORKFLOW.md before dispatch. JSON request on stdin: status, usage, plan, prepare, prefer, clear-preference, bind, finish, report-failure. plan/prepare accept exclude_routes.')
    parser.add_argument('--home', default=os.environ.get('CHIEF_RUNWAY_HOME', '~/.chief-of-staff/runway'))
    parser.add_argument('--server', default=os.environ.get('OPENCODE_SERVER_URL'))
    parser.add_argument('--tarmac', default='http://127.0.0.1:8767')
    args = parser.parse_args()
    root = Path(args.home).expanduser()
    ledger = None
    try:
        config = json.loads((root / 'routes.json').read_text())
        validate(config)
        req = json.load(sys.stdin)
        promo_action = req['action'].startswith('promo-')
        if req['action'] in ('plan', 'prepare') and (req.get('task', {}).get('api_required') or
                req.get('task', {}).get('route') in ('api-fable', 'api-opus', 'api-haiku-proof')):
            req['action'] = 'promo-' + req['action']
            promo_action = True
        if promo_action:
            from .promo import Credit, credit_line, plan
            from .promo_native import Native, dispatch, bind, send, claim_send, collect
            if req['action'] in ('promo-plan', 'promo-prepare'):
                selected = plan(req['task'])['selected']
                if not any(all(route.get(k) == selected.get(k) for k in ('model', 'variant', 'purpose'))
                           and route.get('id') == selected['route'] for route in config.get('api_routes', [])):
                    raise ValueError('promo route not configured; review local api_routes and available model IDs first')
            if req['action'] == 'promo-plan':
                print(json.dumps(plan(req['task'])))
                return 0
            if not (root / 'promo.sqlite3').is_file():
                raise ValueError('parent-authorized promo initialization required')
            credit = Credit(root / 'promo.sqlite3')
            try:
                action = req['action']
                if action == 'promo-status':
                    result = credit.status(time.time())
                    if req.get('format') != 'json':
                        result = Text(credit_line(result))
                elif action == 'promo-prepare':
                    result = credit.prepare(req['task'], time.time())
                elif action == 'promo-dispatch':
                    result = dispatch(credit, req['attempt'], req['text'], Native())
                elif action == 'promo-bind':
                    result = bind(credit, req['attempt'], req['session'], Native())
                elif action == 'promo-send':
                    result = send(credit, req['attempt'], req['text'], Native())
                elif action == 'promo-claim-send':
                    result = claim_send(credit, req['attempt'], req['text'], Native())
                elif action == 'promo-settle':
                    result = collect(credit, req['attempt'], Native())
                else:
                    raise ValueError('unsupported promo action')
                print(result if isinstance(result, Text) else json.dumps(result, allow_nan=False))
            finally:
                credit.close()
            return 0
        registered = registration()
        server = args.server or config.get('server') or (registered[0]['url'] if len(registered) == 1 else None)
        if server:
            host = LocalAPI(server, auth=True)
        elif req['action'] in ('status', 'usage', 'prefer', 'clear-preference', 'report-failure'):
            host = None
        else:
            raise ValueError('native OpenCode server required: use runway tool or --server http://127.0.0.1:PORT')
        ledger = Ledger(root / 'ledger.sqlite3')
        result = handle(req, config, ledger, LocalAPI(args.tarmac), host)
        if req['action'] in ('status', 'usage') and (root / 'promo.sqlite3').exists():
            from .promo import Credit, credit_line
            credit = Credit(root / 'promo.sqlite3')
            try:
                status = credit.status(time.time())
                if isinstance(result, Text):
                    result = Text(str(result) + '\n' + credit_line(status))
                elif isinstance(result, dict):
                    result['credit'] = status
            finally:
                credit.close()
        print(result if isinstance(result, Text) else json.dumps(result, allow_nan=False, separators=(',', ':')))
        return 0
    except Exception as exc:
        # No raw HTTP body, credentials, provider errors, or request text in logs.
        print(json.dumps({'error': 'Runway request failed; no automatic resend; check input, approval and attempt state',
                          'error_type': type(exc).__name__,
                          'dispatch_allowed': False}))
        return 1
    finally:
        if ledger:
            ledger.close()
