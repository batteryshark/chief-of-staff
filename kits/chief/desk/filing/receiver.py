"""Optional filing ledger. No native client, model, network or report execution.

All JSON/native observations are caller-supplied evidence, NOT authentication.
Run only in a trusted operator-owned private root staged by stage.py.
"""
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

import questions_policy as qp

ROOT = Path(__file__).absolute().parent
HEADER = '# Desk filing digest — attributed reports'
LIMIT = 3000  # installed managed Knowledge Note body: JavaScript String.length
WHITESPACE = '\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'


def require(ok, message):
    if not ok:
        raise ValueError('STOP ' + message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=unique)


def digest(value):
    return body_hash(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')))


def body_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def units(text):
    return len(text.encode('utf-16-le')) // 2


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(text):
    value = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    require(value.utcoffset() is not None, 'timezone required')
    return value


def scope(directory):
    return 'path_' + base64.b64encode(directory.encode()).decode().rstrip('=')


def metadata(path, directory=False):
    s = path.lstat()
    require(s.st_uid == os.getuid(), 'wrong UID')
    require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode), 'link/type')
    require(stat.S_IMODE(s.st_mode) == (0o700 if directory else 0o600), 'private mode')
    if not directory:
        require(s.st_nlink == 1, 'hardlink')


def read(name):
    path = ROOT / name
    metadata(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        return loads(f.read())


def save(state):
    metadata(ROOT, True)
    metadata(ROOT / 'state.json')
    fd, temp = tempfile.mkstemp(prefix='.state-', dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, ROOT / 'state.json')
        fd = os.open(ROOT, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def validate_report(r):
    require(isinstance(r, dict) and set(r) == {'kind', 'report_id', 'project', 'lead_session', 'observed', 'landed', 'next', 'your_part', 'questions'}, 'report schema')
    require(r['kind'] == 'status', 'status only')
    require(isinstance(r['report_id'], str) and 1 <= len(r['report_id']) <= 160 and r['report_id'].strip() == r['report_id'] and not any(x in r['report_id'] for x in '\r\n'), 'report ID')
    for key in ('project', 'lead_session', 'observed', 'landed', 'next'):
        require(isinstance(r[key], str) and bool(r[key]), key)
    require(r['your_part'] is None or isinstance(r['your_part'], str), 'your_part')
    qp.questions(r)
    require(timestamp(r['observed']) <= dt.datetime.now(dt.timezone.utc), 'future observation')


def projection(s):
    p = s.get('pending')
    actions = p['actions'] if p else []
    result = {'action': actions[0] if actions else 'done', 'queued_action_types': [a['type'] for a in actions], 'forward_planned': any(a['type'] == 'forward' for a in actions), 'queue_count': len(s['queue']), 'retained_count': len(s['admissions'])}
    if actions:
        result.update(report_id=p['report']['report_id'], action_hash=digest(actions[0]), admitted=bool(p.get('admission')))
        if 'body' in actions[0]:
            result['planned_body_sha256'] = body_hash(actions[0]['body'])
    return result


def finish(s):
    p = s['pending']
    if not p['actions']:
        p.update(state='filed', completed_at=now())
        s['receipts'][p['report']['report_id']] = p
        s['pending'] = None


def note_entry(s, p, a, note):
    owned = [e['note_id'] for group in ('projects', 'digests') for e in s[group].values()]
    require(a.get('id') or note['id'] not in owned, 'cross-kind owned ID collision')
    entry = {'note_id': note['id'], 'body': note['body'], 'body_hash': body_hash(note['body'])}
    if a['type'] == 'status':
        entry['observed'] = p['report']['observed']
        s['projects'][a['directory']] = entry
    else:
        s['digests'][a['directory']] = entry


def recent_digest(history):
    # Full original milestones are retained in immutable admissions, not this view.
    selected = []
    for line in reversed(history):
        if units(HEADER + '\n\n' + '\n'.join([line] + selected)) > LIMIT:
            break
        selected.insert(0, line)
    require(bool(selected), 'single digest milestone exceeds native limit')
    return HEADER + '\n\n' + '\n'.join(selected)


def plan(c, s, item):
    r = item['report']
    key = r['project']
    reg = c['projects'].get(key)
    require(reg and reg['enabled'] and reg['lead_session'] == r['lead_session'], 'unregistered/disabled project or lead; original retained')
    old = s['projects'].get(key, reg.get('handover', {}))
    stale = bool(old.get('observed') and timestamp(r['observed']) <= timestamp(old['observed']))
    actions = []
    if not stale:
        body = '# Desk status — ' + reg['title'] + '\n\nAttributed lead report; not independently verified.\n\n**Landed:** ' + r['landed'] + '\n\n**Next:** ' + r['next'] + '\n\n**Your part:** ' + (r['your_part'] if r['your_part'] is not None else 'Nothing requested.') + '\n\nLead: ' + r['lead_session'] + '\nObserved: ' + r['observed'] + '\nReport: ' + r['report_id']
        body = body.strip(WHITESPACE)
        require(units(body) <= LIMIT, 'status exceeds native body limit; original retained')
        actions.append({'type': 'status', 'directory': key, 'id': old.get('note_id'), 'expected': old.get('body'), 'body': body})
    line = r['report_id'] + ' | ' + r['observed'] + ' | ' + reg['title'] + ' | ' + ('stale; status unchanged' if stale else 'lead reports: ' + r['landed'])
    # Rebuild bounded recent view from full admitted originals in receive order.
    history = [v['digest_line'] for v in s['receipts'].values() if v.get('report', {}).get('project') == key and v.get('digest_line')]
    d = s['digests'].get(key, {})
    actions.append({'type': 'digest', 'directory': key, 'id': d.get('note_id'), 'expected': d.get('body'), 'body': recent_digest(history + [line.strip(WHITESPACE)])})
    qs = qp.questions(r)
    if qs:
        actions.append({'type': 'forward', 'target': c['chief'], 'text': 'Desk forwarding only; NO answer or approval. Project: ' + key + '; lead: ' + r['lead_session'] + '; reportID: ' + r['report_id'] + '\nOriginal verbatim question/request fields:\n' + '\n'.join(qs)})
    s['pending'] = {**item, 'stale': stale, 'digest_line': line, 'actions': actions, 'completed': [], 'question_policy': 'explicit questions[] only; your_part is status only'}
    s['queue'].pop(0)


def actual_notes(a, raw):
    require(raw.get('ok') is True and raw.get('action') == 'knowledge.list', 'actual Knowledge list required')
    require(raw['data']['projectId'] == scope(a['directory']), 'wrong native scope')
    notes = raw['data']['notes']
    require(isinstance(notes, list) and len({n['id'] for n in notes}) == len(notes), 'ambiguous Note IDs')
    return notes


def validate_saved(a, req):
    require(req.get('native_outcome') == 'confirmed_success', 'unknown native outcome')
    raw = req['result']['native_result']
    require(req['result'].get('directory') == a['directory'], 'wrong scope')
    require(raw.get('ok') is True and raw.get('action') == 'knowledge.save', 'successful native save required')
    require(raw['data']['projectId'] == scope(a['directory']), 'wrong native scope')
    note = raw['data']['note']
    require(isinstance(note.get('id'), str) and bool(note['id']), 'missing Note ID')
    require(not a.get('id') or note['id'] == a['id'], 'wrong owned ID')
    require(note.get('body') == a['body'] and req['result'].get('actual_body_sha256') == body_hash(note['body']), 'actual body/hash mismatch')
    return note


def operate(c, s, req, persist=lambda s: None):
    """Small source-test interface; persist durably BEFORE any execute_once result."""
    op = req['op']
    if op == 'inspect':
        return projection(s)
    if op == 'prepare':
        r = req['report']
        validate_report(r)
        rid, h = r['report_id'], digest(r)
        if rid in s['admissions']:
            require(s['admissions'][rid]['hash'] == h, 'changed body under same ID')
            if rid in s['receipts']:
                return {'action': 'duplicate', 'report_id': rid, 'queued_action_types': [], 'forward_planned': False}
        else:
            item = {'report': r, 'hash': h, 'received': now(), 'source_native_id': req.get('source_native_id')}
            s['admissions'][rid] = item
            s['queue'].append(item)
            persist(s)
        if c['mode'] != 'LIVE' or s.get('pending'):
            return projection(s)
        # Always plan the earliest retained original, not the newest message.
        plan(c, s, s['queue'][0])
        persist(s)
        return projection(s)
    require(c['mode'] == 'LIVE', 'disabled/paused; no actions')
    if op == 'drain':
        if not s.get('pending') and s['queue']:
            plan(c, s, s['queue'][0])
            persist(s)
        return projection(s)
    p = s.get('pending')
    require(p and p['actions'], 'no pending action')
    a = p['actions'][0]
    require(req.get('action_hash') == digest(a), 'stale/wrong/duplicate action hash')
    # Registration is operator-only and must remain valid at every admission.
    reg = c['projects'].get(p['report']['project'])
    require(reg and reg['enabled'] and reg['lead_session'] == p['report']['lead_session'], 'registration changed')
    if op == 'question_review':
        require(a['type'] == 'forward' and not p.get('admission'), 'wrong/unknown question action')
        review = qp.review(p['report'], s['receipts'], c['open_source'], req.get('source'), req.get('open_text'), req.get('source_sha256'), req.get('classification'), req.get('evidence'))
        p['question_review'] = {**review, 'action_hash': digest(a), 'source_sha256': req.get('source_sha256')}
        if review['state'] == 'deduplicated':
            p.setdefault('suppressed_actions', []).append({'action': p['actions'].pop(0), 'reason': review['reason'], 'at': now()})
            finish(s)
        persist(s)
        return {**projection(s), 'question_review': review}
    if op == 'admit':
        if a['type'] == 'forward':
            require(not p.get('admission'), 'unknown forward admission')
            review = p.get('question_review', {})
            require(qp.questions(p['report']) and review.get('state') == 'eligible' and review.get('action_hash') == digest(a), 'question eligibility pending')
            require(req.get('source') == c['open_source'] and isinstance(req.get('open_text'), str) and body_hash(req['open_text']) == review['source_sha256'], 'chief-open source changed/unknown')
            require(req.get('current_chief') == c['chief'] == a['target'], 'current chief route mismatch')
        else:
            notes = actual_notes(a, req['native_readback'])
            heading = '# Desk status — ' if a['type'] == 'status' else HEADER + '\n'
            candidates = [n for n in notes if p['report']['report_id'] in n['body'] and n['body'].startswith(heading)] if not a.get('id') else []
            require(len(candidates) <= 1, 'ambiguous first create')
            matches = [n for n in notes if n['id'] == a['id']] if a.get('id') else [n for n in candidates if n['body'] == a['body'] and n.get('origin', {}).get('sessionId') == c['receiver_id']]
            if len(matches) == 1 and matches[0]['body'] == a['body']:
                require(a.get('id') or p.get('admission', {}).get('action_hash') == digest(a), 'unknown first-create admission')
                note_entry(s, p, a, matches[0])
                p['completed'].append({'action': a, 'result': {'native_readback': req['native_readback'], 'reconciled_existing': True}, 'at': now()})
                p['actions'].pop(0)
                p.pop('admission', None)
                finish(s)
                persist(s)
                return projection(s)
            require(not p.get('admission'), 'admitted write not proved saved')
            if a.get('id'):
                require(len(matches) == 1 and matches[0]['body'] == a['expected'], 'contradictory owned body')
            else:
                require(not matches and not candidates, 'ambiguous first create')
        p['admission'] = {'action_hash': digest(a), 'at': now(), 'native_readback': req.get('native_readback')}
        persist(s)
        return {**projection(s), 'execute_once': True}
    require(op == 'ack', 'unknown operation')
    require(p.get('admission', {}).get('action_hash') == digest(a), 'ACK without admission')
    if a['type'] in ('status', 'digest'):
        note = validate_saved(a, req)
        note_entry(s, p, a, note)
    else:
        result = req['result']
        require(req.get('native_outcome') == 'confirmed_success' and result.get('dispatched') is True and result.get('session_id') == a['target']['session_id'] and result.get('dispatch_result'), 'unknown/wrong forward result')
    p['completed'].append({'action': p['actions'].pop(0), 'result': req['result'], 'at': now()})
    p.pop('admission', None)
    finish(s)
    persist(s)
    return projection(s)


def main():
    from stage import safe_chain
    safe_chain(ROOT)
    metadata(ROOT, True)
    metadata(ROOT / 'control.json')
    metadata(ROOT / 'writer.lock')
    # Dedicated lock survives atomic state replacement. Shared with operator.
    fd = os.open(ROOT / 'writer.lock', os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from stage import validate_config
        c = read('control.json')
        validate_config(c)
        req = loads(sys.stdin.read())
        # Source observations are read internally from exactly configured files.
        if req['op'] in ('question_source', 'question_review', 'admit'):
            require(c['mode'] == 'LIVE', 'disabled/paused question source or action')
            if req['op'] == 'question_source' or req.get('source') is not None:
                require(req.get('source') == c['open_source'], 'wrong chief-open source')
                try:
                    text = Path(c['open_source']).read_text()
                except OSError:
                    text = None
                if req['op'] == 'question_source':
                    print(json.dumps({'source': c['open_source'], 'body': text, 'source_sha256': body_hash(text) if text is not None else None, 'eligible': False}))
                    return
                require(text is not None and req.get('source_sha256') == body_hash(text), 'unknown/changed chief-open source')
                req['open_text'] = text
            if req['op'] == 'admit' and req.get('current_chief') is not None:
                require(loads(Path(c['chief_pointer']).read_text()) == c['chief'], 'current chief pointer changed')
        print(json.dumps(operate(c, read('state.json'), req, save), ensure_ascii=False))


if __name__ == '__main__':
    main()
