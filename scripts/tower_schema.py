"""Strict projection v1; kept compatible with Tower project_schema, no I/O."""
import re
from datetime import datetime, timezone


def obj(x, fields):
    if type(x) is not dict or set(x) - set(fields.split()):
        raise ValueError('invalid object fields')
    return x


def text(x, cap=500, empty=False):
    if type(x) is not str or len(x) > cap or (not empty and not x.strip()) or any(ord(c) < 32 and c not in '\n\r\t' for c in x):
        raise ValueError('invalid text')
    return x


def ident(x):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', text(x, 80)):
        raise ValueError('invalid ID')
    return x


def seq(x, cap):
    if type(x) is not list or len(x) > cap:
        raise ValueError('invalid list')
    return x


def stamp(x):
    text(x, 40)
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)', x):
        raise ValueError('invalid timestamp')
    t = datetime.fromisoformat(x.replace('Z', '+00:00'))
    if not 2000 <= t.year <= 2100 or t > datetime.now(timezone.utc):
        raise ValueError('invalid timestamp')
    return t


def evidence(x):
    text(x.get('reference')); text(x.get('provenance'))


def bound(x, project, outcome):
    if ident(x.get('project_id')) != project or ident(x.get('outcome_id')) != outcome:
        raise ValueError('identity mismatch')


def depth(x, n=0):
    if n > 12:
        raise ValueError('nesting limit')
    for v in x.values() if type(x) is dict else x if type(x) is list else []:
        depth(v, n+1)


def projection(x, project, outcome):
    depth(x)
    obj(x, 'version project_id outcome_id generated_at summary knowledge acceptance activity')
    if type(x.get('version')) is not int or x['version'] != 1:
        raise ValueError('invalid version')
    bound(x, project, outcome)
    generated = stamp(x.get('generated_at'))
    if 'summary' in x:
        s = x['summary']
        if type(s) is not dict: raise ValueError('invalid summary')
        if set(s) - {'observed_at','provenance','reference','usable now','left','waiting on','handed to','needs_you'}:
            raise ValueError('invalid summary fields')
        if 'needs_you' in s and type(s['needs_you']) is not bool: raise ValueError('invalid needs_you')
        evidence(s)
        if stamp(s.get('observed_at')) > generated:
            raise ValueError('summary after generation')
        for k in ('usable now','left','waiting on','handed to'):
            if k in s: text(s[k], 2000)
    if 'knowledge' in x:
        k = obj(x['knowledge'], 'state provenance items observed_at')
        if 'observed_at' in k and stamp(k['observed_at']) > generated:
            raise ValueError('knowledge after generation')
        text(k.get('provenance'))
        if k.get('state') not in ('available','unavailable') or (k['state'] == 'unavailable' and 'items' in k):
            raise ValueError('invalid knowledge state')
        seen = set()
        for i in seq(k.get('items', []), 200):
            obj(i, 'id kind title body completed')
            iid = ident(i.get('id'))
            if iid in seen or i.get('kind') not in ('note','todo','plan'): raise ValueError('invalid item')
            seen.add(iid); text(i.get('title'), 200); text(i.get('body'), 50000, True)
            if (i['kind'] == 'todo' or 'completed' in i) and type(i.get('completed')) is not bool:
                raise ValueError('invalid completion')
    if 'acceptance' in x:
        a = obj(x['acceptance'], 'project_id outcome_id state request_state request_id requested_at provenance reference answer')
        bound(a, project, outcome); evidence(a)
        if a.get('state') not in ('unfinished','finished-awaiting-acceptance','accepted','not-yet') or a.get('request_state') not in ('none','pending','expired','cancelled','answered'):
            raise ValueError('invalid acceptance')
        if a['request_state'] == 'none':
            if 'request_id' in a or 'requested_at' in a: raise ValueError('unexpected request')
        else:
            ident(a.get('request_id')); requested = stamp(a.get('requested_at'))
            if requested > generated: raise ValueError('future request')
        if a['request_state'] == 'answered':
            b = obj(a.get('answer'), 'type id request_id project_id outcome_id value answered_at reference provenance')
            bound(b, project, outcome); evidence(b); ident(b.get('id'))
            if b.get('type') != 'nod.answer' or b.get('request_id') != a['request_id'] or not requested <= stamp(b.get('answered_at')) <= generated:
                raise ValueError('invalid answer binding')
            if a['state'] not in ('accepted','not-yet') or b.get('value') != {'accepted':'Accept','not-yet':'Not yet'}[a['state']]:
                raise ValueError('invalid answer value')
        elif a.get('answer') is not None or a['state'] in ('accepted','not-yet'):
            raise ValueError('no actual answer')
    seen = set()
    for e in seq(x.get('activity', []), 500):
        obj(e, 'id project_id outcome_id kind at label reference provenance')
        bound(e, project, outcome); evidence(e); iid = ident(e.get('id')); text(e.get('label'))
        if iid in seen or e.get('kind') not in ('landing','acceptance','decision','handoff') or stamp(e.get('at')) > generated:
            raise ValueError('invalid activity')
        seen.add(iid)
    return x
