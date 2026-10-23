"""Pure routing decisions. Percent reservations are conservative heuristics, not token forecasts."""
import math
from datetime import datetime, timezone

VERSION = 1
SIZES = {'small': 1.0, 'medium': 3.0, 'large': 8.0}
CATEGORIES = {'trivial', 'research', 'implement', 'hard'}


def instant(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def timestamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def validate(config):
    if config.get('version') != VERSION:
        raise ValueError('route configuration version must be 1')
    seen = set()
    pools = {}
    for r in config.get('routes', []):
        for key in ('id', 'host', 'model', 'source', 'provider', 'pool'):
            if not isinstance(r.get(key), str) or not r[key]:
                raise ValueError(f'route requires {key}')
        if r['host'] != 'local':
            raise ValueError('this dispatcher supports the local host; remote accounts require a separate verified registry')
        blocked = r.get('unavailable_transports', [])
        if not isinstance(blocked, list) or any(t != 'openchamber' for t in blocked):
            raise ValueError('unavailable_transports supports only openchamber')
        if r['id'] in seen:
            raise ValueError('duplicate route id')
        seen.add(r['id'])
        if 'account' not in r or not isinstance(r['account'], str):
            raise ValueError('route must pin the Tarmac account label, including an empty label')
        if not isinstance(r.get('categories'), list) or not r['categories'] or not set(r['categories']) <= CATEGORIES:
            raise ValueError('route requires supported task categories')
        windows = r.get('windows')
        if windows != 'all' and (not isinstance(windows, list) or not windows
                                or any(not isinstance(w, str) or not w for w in windows)):
            raise ValueError('windows must be all or a nonempty list of exact window ids')
        for key, default, low, high in (('reserve_percent', 5, 0, 99),
                                      ('max_parallel', 2, 1, 16), ('priority', 0, -100, 100)):
            n = r.get(key, default)
            if not number(n) or not low <= n <= high:
                raise ValueError(f'invalid {key}')
        if int(r.get('max_parallel', 2)) != r.get('max_parallel', 2):
            raise ValueError('max_parallel must be an integer')
        # A source's aliases cannot evade its common admission cap.
        identity = (r['provider'], r['account'])
        pool = (r['pool'], r.get('max_parallel', 2))
        if identity in pools and pools[identity] != pool:
            raise ValueError('routes for the same source must share pool and max_parallel')
        pools[identity] = pool


def source_for(snapshot, route):
    found = [s for s in snapshot.get('sources', [])
             if route['source'] in (s.get('id'), s.get('slug'))]
    if len(found) != 1:
        raise ValueError('mapped quota source is missing or ambiguous')
    s = found[0]
    if (s.get('provider'), s.get('account')) != (route['provider'], route['account']):
        raise ValueError('quota account/provider mapping changed')
    if s.get('enabled') is not True or s.get('archived') or s.get('needs_login'):
        raise ValueError('quota source disabled, archived or needs login')
    if s.get('kind') != 'plan':
        raise ValueError('automatic paid API fallback is not configured')
    return s


def live_windows(snapshot, route, now):
    s = source_for(snapshot, route)
    latest = s.get('latest') or {}
    at, until = instant(latest.get('observed_at')), instant(latest.get('fresh_until'))
    if at is None or at > now + 5 or now - at > 3600 or until is None or until <= now:
        raise ValueError('quota observation is missing or stale; refresh this source once')
    if latest.get('reason') or latest.get('needs_login'):
        raise ValueError('quota observation failed or is only a historical fallback')
    all_windows = latest.get('windows') or []
    by_id = {w['id']: w for w in all_windows}
    if len(by_id) != len(all_windows):
        raise ValueError('ambiguous quota window ids')
    ids = list(by_id) if route['windows'] == 'all' else route['windows']
    if not ids or any(w not in by_id for w in ids):
        raise ValueError('required quota window missing; capacity is unknown')
    result = []
    for wid in ids:
        w = by_id[wid]
        remaining, reset = w.get('remaining_percent'), instant(w.get('resets_at'))
        if w.get('unit') != 'percent' or not number(remaining) or not 0 <= remaining <= 100:
            raise ValueError(f'{wid}: missing or invalid percentage')
        if w.get('stale') or (w.get('resets_at') and reset is None) or (reset is not None and reset <= now):
            raise ValueError(f'{wid}: reset passed or observation is stale')
        result.append(w)
    return s, latest, result


def preference_active(preference, scope, source, windows, now):
    if not preference or preference.get('scope') != scope or preference.get('source_id') != source['id']:
        return False
    expiry = instant(preference.get('expires_at'))
    if expiry is None or expiry <= now:
        return False
    return any(w['id'] == preference['window_id'] and
               instant(w.get('resets_at')) == instant(preference['reset_at']) for w in windows)


def held_percent(attempts, pool, window):
    """Admission headroom, not billing; clamp estimates to observed remaining.

    Idle uncertainty may release quota without releasing source/action ownership.
    """
    total = 0
    for a in attempts:
        if a['pool'] != pool or a['state'] not in ('admitted', 'running', 'uncertain'):
            continue
        if a['state'] == 'uncertain' and a.get('usage_released') is True:
            continue
        for charge in a['reservation']:
            if charge['window_id'] == window['id'] and instant(charge['reset_at']) == instant(window.get('resets_at')):
                total += charge['percent']
    return min(window['remaining_percent'], max(0, total))


def validate_exclusions(config, exclude_routes):
    if not isinstance(exclude_routes, list) or any(not isinstance(r, str) for r in exclude_routes):
        raise ValueError('exclude_routes must be a list of configured route ids')
    if set(exclude_routes) - {r['id'] for r in config['routes']}:
        raise ValueError('exclude_routes contains an unknown route id')


def decide(config, snapshot, catalog, task, attempts, preference, now, burning=(), *, exclude_routes=None, cooldowns=()):
    """burning: source ids whose allowance would go unspent at its reset (see usage.assess).
    They are preferred automatically, after an explicit use-before-reset request."""
    validate(config)
    exclude_routes = [] if exclude_routes is None else exclude_routes
    validate_exclusions(config, exclude_routes)
    if task.get('category') not in CATEGORIES or task.get('size') not in SIZES:
        raise ValueError('task requires category and size (small, medium, large)')
    if not task.get('scope') or not task.get('directory') or not task.get('job'):
        raise ValueError('task requires scope, directory and stable job id')
    if snapshot.get('schema_version') != 2 or snapshot.get('passive') is not True:
        raise ValueError('Tarmac passive snapshot v2 is required')
    if catalog.get('directory') != task['directory']:
        raise ValueError('catalog must belong to the worker directory')
    catalog_at = instant(catalog.get('observed_at'))
    if catalog_at is None or not 0 <= now - catalog_at <= 60:
        raise ValueError('target model catalog is stale')
    models = {f"{m['providerID']}/{m['id']}": m for m in catalog.get('models', [])}
    candidates, rejected = [], []
    for r in config.get('routes', []):
        try:
            # Current Ledger.plan emits only OpenChamber create/send actions.
            if 'openchamber' in r.get('unavailable_transports', []):
                raise ValueError('OpenChamber transport unavailable: selectable alias validation repair required')
            if r['id'] in exclude_routes:
                raise ValueError('excluded by this request')
            cooling = [c for c in cooldowns if (c['host'], c['pool'], c['model']) ==
                       (r['host'], r['pool'], r['model']) and instant(c['until']) > now]
            if cooling:
                c = max(cooling, key=lambda c: instant(c['until']))
                raise ValueError(f"model cooldown until {c['until']}: {c['reason']} ({c['reset_basis']})")
            if task['category'] not in r['categories']:
                raise ValueError('below the configured task capability requirement')
            m = models.get(r['model'])
            if not m or m.get('enabled') is not True or m.get('status') not in ('active', 'beta', 'alpha'):
                raise ValueError('model unavailable in target catalog')
            if r.get('variant') and r['variant'] not in [v['id'] for v in m.get('variants', [])]:
                raise ValueError('configured thinking variant unavailable')
            if task.get('tools', True) and not m.get('capabilities', {}).get('tools'):
                raise ValueError('model does not support tools')
            if not set(task.get('input', ['text'])) <= set(m.get('capabilities', {}).get('input', [])):
                raise ValueError('required input modality unavailable')
            context = task.get('context', 0)
            if not number(context) or context < 0 or context > m.get('limit', {}).get('context', 0):
                raise ValueError('required context unavailable')
            source, latest, windows = live_windows(snapshot, r, now)
            active = [a for a in attempts if a['pool'] == r['pool'] and a['state'] in ('admitted', 'running', 'uncertain')]
            if len(active) >= r.get('max_parallel', 2):
                raise ValueError('shared pool concurrency limit reached')
            preferred = preference_active(preference, task['scope'], source, windows, now)
            reservation, headroom = [], []
            estimate = SIZES[task['size']]
            for w in windows:
                reset = instant(w.get('resets_at'))
                reserved = held_percent(attempts, r['pool'], w)
                floor = 0 if preferred and w['id'] == preference['window_id'] else r.get('reserve_percent', 5)
                available = w['remaining_percent'] - reserved - floor
                if w['remaining_percent'] <= 0 or available < estimate:
                    raise ValueError(f"{w['id']}: insufficient headroom after reservations and reserve")
                hours = max(1, min(168, (reset - now) / 3600)) if reset else 168
                headroom.append((available - estimate) / hours)
                reservation.append({'window_id': w['id'], 'reset_at': w.get('resets_at'), 'percent': estimate})
            candidates.append({'route': r['id'], 'model': r['model'], 'variant': r.get('variant'),
                'agent': r.get('agent'), 'host': r['host'], 'pool': r['pool'], 'source_id': source['id'],
                'provider': r['provider'], 'account': r['account'],
                'observed_at': latest['observed_at'], 'reservation': reservation,
                'score': min(headroom), 'priority': r.get('priority', 0), 'preferred': preferred,
                'burning': source['id'] in burning,
                'reason': 'Prioritize this allowance before its reset' if preferred else
                          'Burn mode: this allowance would go unspent at its reset' if source['id'] in burning else
                          'Task fits; all mapped windows have reserved headroom',
                'estimate_kind': 'fixed percentage heuristic; not a token or completion guarantee'})
        except ValueError as exc:
            rejected.append({'route': r['id'], 'reason': str(exc)})
    candidates.sort(key=lambda c: (-int(c['preferred']), -int(c['burning']), -c['score'], -c['priority'], c['route']))
    return {'policy_version': VERSION, 'selected': candidates[0] if candidates else None,
            'alternatives': candidates[1:], 'rejected': rejected}
