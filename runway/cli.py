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
from .policy import timestamp, validate, instant
from .usage import assess, burn_lines, table


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

    def idle_evidence(self, sid, expected_directory):
        path = '/api/session/' + urllib.parse.quote(sid, safe='')
        info = self.session(sid)
        if info.get('location', {}).get('directory') != expected_directory:
            raise ValueError('session moved; reconcile its worktree before releasing admission')
        active = self.get('/api/session/active')['data']
        pending = self.get(path + '/inbox')['data']
        permissions = self.get(path + '/permission')['data']
        forms = self.get(path + '/form')['data']
        # These are independent observations, not a native lock. Recheck immediately before sending.
        idle = info.get('time', {}).get('idle')
        idle_at = timestamp(idle / 1000) if isinstance(idle, (int, float)) else idle
        return {'last_idle_at': idle_at, 'session_id': sid, 'idle': sid not in active, 'inbox_empty': not pending and not permissions and not forms,
                'outcome': info.get('outcome'), 'observed_at': timestamp(time.time())}


def handle(req, config, ledger, quota, host):
    action = req['action']
    if action == 'status':
        if req.get('format') == 'json':
            return {'attempts': ledger.attempts(), 'preference': ledger.preference(req.get('scope', '')),
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
        task = dict(req['task'])
        task['directory'] = str(Path(task['directory']).expanduser().resolve(strict=True))
        # Fetch both within this request; do not accept caller-supplied availability.
        snapshot = quota.get('/api/v1/snapshot')
        catalog = host.catalog(task['directory'], [r['model'] for r in config['routes']])
        if action == 'prepare':
            previous = [a for a in ledger.attempts() if a['scope'] == task['scope'] and a['job'] == task['job']]
            if previous and previous[-1]['state'] == 'quiescent':
                evidence = host.idle_evidence(previous[-1]['session_id'], task['directory'])
                if not evidence['idle'] or not evidence['inbox_empty']:
                    raise ValueError('continuation session became active or has queued work; reconcile it first')
        result = ledger.plan(config, snapshot, catalog, task, time.time(), admit=action == 'prepare')
        return result if req.get('format') == 'json' else compact_plan(result)
    if action == 'bind':
        return compact_attempt(ledger.bind(req['attempt'], host.session(req['session']), time.time()), req)
    if action == 'finish':
        a = ledger.get(req['attempt'])
        evidence = {key: req.get(key) for key in ('confirmed_not_sent', 'tools_reconciled', 'effects_reconciled')}
        if req['state'] not in ('unsent', 'uncertain'):
            if not a.get('session_id'):
                raise ValueError('bind the confirmed session before releasing this attempt')
            evidence.update(host.idle_evidence(a['session_id'], a['task']['directory']))
        checkpoint = dict(req.get('checkpoint') or {})
        if checkpoint.get('directory'):
            checkpoint['directory'] = str(Path(checkpoint['directory']).expanduser().resolve())
        return compact_attempt(ledger.finish(req['attempt'], req['state'], checkpoint, evidence, time.time()), req)
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
        lines.append(f"- {a['job']} | {a['state']} | {a['route']} | session {a.get('session_id') or 'none'} | attempt {a['id']}")
    lines.append('Routes: ' + '; '.join(f"{r['id']}={r['model']}" + (f" {r['variant']}" if r.get('variant') else '')
                                         + f" [{','.join(r['categories'])}]" for r in config.get('routes', [])) + '.')
    return '\n'.join(lines)


def compact_attempt(a, req):
    if req.get('format') == 'json':
        return a
    keep = ('id', 'job', 'state', 'route', 'model', 'variant', 'session_id', 'message_id')
    return {k: a.get(k) for k in keep if a.get(k) is not None}


def compact_plan(result):
    """What an agent needs to dispatch: the choice, the exact args, and one line per alternative."""
    out = {'dispatch_allowed': result.get('dispatch_allowed', False)}
    sel = result.get('selected')
    if sel:
        out['selected'] = {k: sel.get(k) for k in ('route', 'model', 'variant', 'reason')}
    for key in ('action', 'args', 'reason', 'attempt_id'):
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
    parser = argparse.ArgumentParser(description='Quota-aware chief-of-staff routing. Read routing/WORKFLOW.md before dispatch. JSON request on stdin: status, usage, plan, prepare, prefer, clear-preference, bind, finish.')
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
        registered = registration()
        server = args.server or config.get('server') or (registered[0]['url'] if len(registered) == 1 else None)
        if server:
            host = LocalAPI(server, auth=True)
        elif req['action'] in ('status', 'usage', 'prefer', 'clear-preference'):
            host = None
        else:
            raise ValueError('native OpenCode server required: use runway tool or --server http://127.0.0.1:PORT')
        ledger = Ledger(root / 'ledger.sqlite3')
        result = handle(req, config, ledger, LocalAPI(args.tarmac), host)
        print(result if isinstance(result, Text) else json.dumps(result, allow_nan=False, separators=(',', ':')))
        return 0
    except Exception as exc:
        # No raw HTTP body, credentials, provider errors, or request text in logs.
        print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                          'dispatch_allowed': False}))
        return 1
    finally:
        if ledger:
            ledger.close()
