"""Usage at dispatch time. Reads the same Tarmac snapshot routing already fetches and finds
allowances that would go unspent at their reset ("burn") and allowances that are nearly gone
("low"). Routing prefers burnable allowances automatically: burn mode is the principal's standing
instruction (2026-10-13). There is no background process; this runs whenever work is dispatched.
"""
from .policy import instant, number

DEFAULTS = {
    'short_window_hours': 24,         # windows this long or shorter are short (the 5-hour kind)
    'short_burn_percent': 50,         # a short window with this much left...
    'short_burn_within_hours': 2,     # ...and a reset this soon is worth burning
    'long_burn_percent': 20,          # a long (weekly) window with this much left...
    'long_burn_within_hours': 24,     # ...and a reset within a day is worth burning
    'other_window_floor_percent': 10, # every other window of the source needs this much left
    'low_percent': 10,                # at or below this, the allowance is running low
}


def strongest(routes):
    hard = [r for r in routes if 'hard' in r.get('categories', [])]
    return sorted(hard or routes, key=lambda r: (r.get('priority', 0), r['id']))[0]


def assess(config, snapshot, now, settings=None):
    """Pure decision: which routed plan allowances to burn and which are running low."""
    s = {**DEFAULTS, **(settings or {})}
    by_source = {}
    for r in config.get('routes', []):
        by_source.setdefault(r['source'], []).append(r)
    burn, low, skipped = [], [], []
    for src in snapshot.get('sources', []):
        routes = by_source.get(src.get('id')) or by_source.get(src.get('slug'))
        if not routes:
            continue
        name = src.get('slug') or src.get('id')
        if src.get('kind') != 'plan':
            skipped.append({'source': name, 'reason': 'paid API source; never burned automatically'})
            continue
        if src.get('enabled') is not True or src.get('archived') or src.get('needs_login'):
            skipped.append({'source': name, 'reason': 'disabled, archived or needs login'})
            continue
        latest = src.get('latest') or {}
        until = instant(latest.get('fresh_until'))
        if latest.get('reason') or until is None or until <= now:
            skipped.append({'source': name, 'reason': 'observation stale or failed'})
            continue
        windows = [w for w in latest.get('windows') or []
                   if w.get('unit') == 'percent' and number(w.get('remaining_percent')) and not w.get('stale')]
        for w in windows:
            remaining = w['remaining_percent']
            reset = instant(w.get('resets_at'))
            if reset is not None and reset <= now:
                continue
            hours = (reset - now) / 3600 if reset is not None else None
            label = w.get('label') or w['id']
            base = {'source': src['id'], 'name': name, 'window': w['id'], 'label': label,
                    'remaining_percent': remaining, 'resets_at': w.get('resets_at'),
                    'hours_left': round(hours, 1) if hours is not None else None}
            if remaining <= s['low_percent'] and (hours is None or hours > 1):
                low.append(base)
            if hours is None:
                continue
            duration = w.get('duration_minutes')
            short = number(duration) and duration / 60 <= s['short_window_hours']
            pct = s['short_burn_percent'] if short else s['long_burn_percent']
            within = s['short_burn_within_hours'] if short else s['long_burn_within_hours']
            if remaining < pct or hours > within:
                continue
            # Another window of the same source that is nearly out, and not about to reset, stops the burn.
            blocked = [o['id'] for o in windows if o is not w
                       and o['remaining_percent'] < s['other_window_floor_percent']
                       and (instant(o.get('resets_at')) is None or instant(o.get('resets_at')) - now > 3600)]
            if blocked:
                skipped.append({**base, 'reason': 'another window is nearly out: ' + ', '.join(blocked)})
                continue
            route = strongest(routes)
            burn.append({**base, 'route': route['id'], 'model': route['model']})
    burn.sort(key=lambda b: (-b['remaining_percent'], b['hours_left'], b['route']))
    return {'burn': burn, 'low': low, 'skipped': skipped, 'choice': burn[0] if burn else None}


def _left(hours):
    if hours is None:
        return ''
    d, h = divmod(int(round(hours)), 24)
    return f'{d}d {h}h' if d else f'{h}h'


def table(config, snapshot, now, settings=None):
    """The usage picture as a few aligned lines, for agents to read before they dispatch work.
    Raw snapshot JSON is never returned by default: it costs thousands of tokens and says less."""
    from datetime import datetime
    result = assess(config, snapshot, now, settings)
    burn = {(b['source'], b['window']) for b in result['burn']}
    low = {(e['source'], e['window']) for e in result['low']}
    routed = {r['source'] for r in config.get('routes', [])}
    rows = [('source', 'window', 'left', 'resets', 'note')]
    for src in snapshot.get('sources', []):
        if src.get('enabled') is not True or src.get('archived'):
            continue
        name = src.get('slug') or src.get('id')
        latest = src.get('latest') or {}
        until = instant(latest.get('fresh_until'))
        stale = bool(latest.get('reason')) or until is None or until <= now
        paid = src.get('kind') != 'plan'
        windows = latest.get('windows') or []
        if paid:
            money = next((w for w in windows if w.get('unit') not in (None, 'percent')), None)
            amount, unit = (money.get('remaining_percent'), money.get('unit')) if money else \
                (latest.get('remaining'), latest.get('unit'))
            left = f'{amount:.2f} {unit}' if number(amount) else '?'
            rows.append((name, 'credit', left, '', 'PAID: only with permission for a project'))
            continue
        for w in windows:
            if w.get('unit') != 'percent' or not number(w.get('remaining_percent')):
                continue
            reset = instant(w.get('resets_at'))
            resets = (datetime.fromtimestamp(reset).strftime('%a %d %b %H:%M') + f' ({_left((reset - now) / 3600)})'
                      if reset is not None and reset > now else 'unknown')
            key = (src.get('id'), w['id'])
            note = 'BURN: use first' if key in burn else 'LOW: avoid for new work' if key in low else ''
            if stale:
                note = 'stale reading'
            elif src.get('id') not in routed and src.get('slug') not in routed:
                note = (note + '; ' if note else '') + 'no route'
            rows.append((name, w.get('label') or w['id'], f"{w['remaining_percent']:g}%", resets, note))
    widths = [max(len(str(r[i])) for r in rows) for i in range(4)]
    lines = ['  '.join(str(c).ljust(widths[i]) if i < 4 else str(c) for i, c in enumerate(r)).rstrip() for r in rows]
    lines.append('Burn now: ' + (', '.join(f"{b['name']} {b['label']} ({b['remaining_percent']:g}% left, "
                                          f"resets in {_left(b['hours_left'])})" for b in result['burn']) or 'none') + '.')
    lines.append('Low: ' + (', '.join(f"{e['name']} {e['label']}" for e in result['low']) or 'none') + '.')
    return '\n'.join(lines)


def burn_lines(result):
    return {'burn': [f"{b['name']} {b['label']}: {b['remaining_percent']:g}% left, resets in {_left(b['hours_left'])}"
                     for b in result['burn']],
            'low': [f"{e['name']} {e['label']}: {e['remaining_percent']:g}% left" for e in result['low']]}
