"""Absent-only JSONC splice installer. Never displays existing config or credentials."""
import fcntl
import hashlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path

from .promo import Credit


class JSONC:
    """Small strict JSON + comments/trailing-comma reader retaining object offsets."""
    def __init__(self, text):
        self.text, self.i, self.objects = text, 0, {}
        self.value = self.parse(())
        self.space()
        if self.i != len(text) or not isinstance(self.value, dict):
            raise ValueError('invalid JSONC document')

    def space(self):
        while self.i < len(self.text):
            if self.text[self.i].isspace():
                self.i += 1
            elif self.text.startswith('//', self.i):
                end = self.text.find('\n', self.i)
                self.i = len(self.text) if end < 0 else end + 1
            elif self.text.startswith('/*', self.i):
                end = self.text.find('*/', self.i + 2)
                if end < 0:
                    raise ValueError('unterminated JSONC comment')
                self.i = end + 2
            else:
                break

    def parse(self, path):
        self.space()
        start = self.i
        ch = self.text[self.i:self.i+1]
        if ch in ('{', '['):
            obj = {} if ch == '{' else []
            close = '}' if ch == '{' else ']'
            self.i += 1
            if ch == '{':
                self.objects[path] = start
            self.space()
            while self.text[self.i:self.i+1] != close:
                if ch == '{':
                    key, end = json.JSONDecoder().raw_decode(self.text, self.i)
                    if not isinstance(key, str) or key in obj:
                        raise ValueError('duplicate/invalid JSONC object key')
                    self.i = end
                    self.space()
                    if self.text[self.i:self.i+1] != ':':
                        raise ValueError('JSONC colon required')
                    self.i += 1
                    obj[key] = self.parse(path + (key,))
                else:
                    obj.append(self.parse(path + (len(obj),)))
                self.space()
                if self.text[self.i:self.i+1] != ',':
                    break
                self.i += 1
                self.space()
            if self.text[self.i:self.i+1] != close:
                raise ValueError('JSONC close required')
            self.i += 1
            return obj
        value, self.i = json.JSONDecoder().raw_decode(self.text, self.i)
        return value


def splice(text, additions, grouped=False):
    doc = JSONC(text)
    groups, root = {}, {}
    for key, value in additions.items():
        if grouped and key in doc.value:
            if not isinstance(doc.value[key], dict) or set(value) & set(doc.value[key]):
                raise ValueError('scoped config collision; parent review required')
            groups[(key,)] = value
        else:
            if key in doc.value:
                raise ValueError('scoped config collision; parent review required')
            root[key] = value
    if root:
        groups[()] = root
    edits = []
    for path, value in groups.items():
        existing = doc.value if not path else doc.value[path[0]]
        fields = ',\n'.join(json.dumps(k) + ': ' + json.dumps(v, indent=2) for k, v in value.items())
        edits.append((doc.objects[path] + 1, '\n' + fields + (',' if existing else '') + '\n'))
    out = text
    for pos, value in sorted(edits, reverse=True):
        out = out[:pos] + value + out[pos:]
    JSONC(out)
    return out, sorted(edits)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def atomic(path, text, mode):
    fd, tmp = tempfile.mkstemp(prefix='.promo-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('symlink/non-file destination refused')
    with path.open(encoding='utf-8', newline='') as f:
        return f.read()


def install(source, config, root, approval, apply=False, now=None):
    now = time.time() if now is None else now
    # Explicit target, no scanning other configs or any auth/key paths.
    config, root = Path(config).absolute(), Path(root).absolute()
    if config.suffix not in ('.json', '.jsonc') or config.name not in ('opencode.json', 'opencode.jsonc'):
        raise ValueError('explicit opencode.json(c) target required')
    sibling = config.with_suffix('.jsonc' if config.suffix == '.json' else '.json')
    if sibling.exists():
        raise ValueError('ambiguous JSON/JSONC targets')
    if not config.parent.is_dir() or not root.is_dir() or root.is_symlink():
        raise ValueError('existing real config parent and Runway directory required')
    routes = root / 'routes.json'
    proposed = json.loads((source / 'routing/api-promo.opencode.json').read_text())
    policy = json.loads((source / 'routing/api-promo.routes.json').read_text())
    documents = [(config, {k: proposed[k] for k in ('providers', 'agents')}, True),
                 (routes, policy, False)]
    manifest, outputs = [], {}
    for path, additions, grouped in documents:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('symlink destination refused')
        exists = path.exists()
        if path == routes and not exists:
            raise ValueError('existing Runway routes config required')
        before = read(path) if exists else '{}\n'
        after, edits = splice(before, additions, grouped)
        mode = stat.S_IMODE(path.stat().st_mode) if exists else 0o600
        manifest.append({'path': str(path), 'existed': exists, 'before': sha(before),
                         'after': sha(after), 'mode': mode, 'edits': edits})
        outputs[path] = after
    database = root / 'promo.sqlite3'
    journal = root / 'promo-install.json'
    if database.exists() or database.is_symlink() or journal.exists() or journal.is_symlink():
        raise ValueError('existing promo counter/install receipt; absent-only install refused')
    # Validate the supplied authority and baseline even in dry-run, without live writes.
    if (approval.get('console_backstop') is not True or approval.get('exclusive_key') is not True
            or not approval.get('reference') or approval.get('baseline_micro_usd') != 0):
        raise ValueError('verified backstop/exclusive-key/baseline authority required')
    from .promo import cycle
    if approval.get('verified_cycle') != cycle(now)[0]:
        raise ValueError('authority cycle does not match current accounting cycle')
    if not apply:
        return {'dry_run': True, 'config_entries': ['providers.anthropic-promo', 'agents.api-promo-review'],
                'runway_entries': ['api_routes', 'promo'], 'counter': 'new separate promo.sqlite3'}
    with (root / '.promo-install.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        if database.exists() or journal.exists():
            raise ValueError('install state changed')
        for item in manifest:
            path = Path(item['path'])
            current = read(path) if path.exists() else '{}\n'
            if (path.exists() != item['existed'] or sha(current) != item['before']
                    or (path.exists() and stat.S_IMODE(path.stat().st_mode) != item['mode'])):
                raise ValueError('config preimage changed')
        # Journal stores only scoped additions/hashes, never existing config values.
        atomic(journal, json.dumps({'files': manifest}), 0o600)
        credit = Credit(database)
        try:
            credit.authorize(now, approval, approval['baseline_micro_usd'])
        finally:
            credit.close()
        for item in manifest:
            path = Path(item['path'])
            current = read(path) if path.exists() else '{}\n'
            if sha(current) != item['before']:
                raise ValueError('config changed during install; scoped rollback required')
            atomic(path, outputs[path], item['mode'])
    return {'installed': True, 'receipt': str(journal), 'dispatch_ready': True}


def unsplice(current, item):
    """Reconstruct in memory only; persist no unrelated preimage values."""
    adjusted, offset = [], 0
    for pos, value in item['edits']:
        adjusted.append((pos + offset, value))
        offset += len(value)
    for pos, value in reversed(adjusted):
        if current[pos:pos+len(value)] != value:
            raise ValueError('scoped amendment mismatch')
        current = current[:pos] + current[pos+len(value):]
    if sha(current) != item['before']:
        raise ValueError('original preimage mismatch')
    return current


def amend(source, config, root, apply=False):
    """Exact owned steps removal / 2048→8192 transition; insertion-only recovery."""
    config, root = Path(config).absolute(), Path(root).absolute()
    if (config.name not in ('opencode.json', 'opencode.jsonc') or root.is_symlink()
            or not root.is_dir() or config.parent.is_symlink()):
        raise ValueError('explicit real config and Runway directory required')
    sibling = config.with_suffix('.jsonc' if config.suffix == '.json' else '.json')
    if sibling.exists() or sibling.is_symlink():
        raise ValueError('ambiguous config target')
    journal = root / 'promo-install.json'
    pending = root / 'promo-amend.json'
    # Dry-run creates no files, including locks. Apply shares the installer lock.
    if apply:
        lock_path = root / '.promo-install.lock'
        if lock_path.is_symlink():
            raise ValueError('symlink lock refused')
        with lock_path.open('a') as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            return _amend_locked(source, config, root, journal, pending, True)
    return _amend_locked(source, config, root, journal, pending, False)


def _amend_locked(source, config, root, journal, pending, apply):
    def private(path):
        value = read(path)
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError('private receipt mode required')
        return json.loads(value)

    receipt = private(journal)
    recovery = private(pending) if pending.exists() or pending.is_symlink() else None
    old = recovery['old'] if recovery else receipt
    if len(old['files']) != 2 or [i['path'] for i in old['files']] != [str(config), str(root / 'routes.json')]:
        raise ValueError('exact original installation receipt required')
    item, routes = old['files']
    current = read(config)
    route_text = read(root / 'routes.json')
    if (sha(route_text) != routes['after']
            or stat.S_IMODE((root / 'routes.json').stat().st_mode) != routes['mode']
            or stat.S_IMODE(config.stat().st_mode) != item['mode']):
        raise ValueError('postimage/mode changed')
    new = json.loads(json.dumps(old))
    proposed = json.loads((source / 'routing/api-promo.opencode.json').read_text())
    additions = {k: proposed[k] for k in ('providers', 'agents')}
    if (set(additions['providers']) != {'anthropic-promo'}
            or set(additions['agents']) != {'api-promo-review'}
            or 'steps' in additions['agents']['api-promo-review']):
        raise ValueError('reviewed no-steps snippet required')
    # On recovery the file may already be the new postimage; reconstruct from its
    # corresponding insertion receipt, never from a saved full config copy.
    active = recovery['new']['files'][0] if recovery and sha(current) == recovery['new']['files'][0]['after'] else item
    if sha(current) != active['after']:
        raise ValueError('postimage changed; no amendment writes')
    original = unsplice(current, active)
    after, edits = splice(original, additions, True)
    if additions['providers']['anthropic-promo']['body']['max_tokens'] != 8192:
        raise ValueError('reviewed 8192 cap required')
    legacy = json.loads(json.dumps(additions))
    legacy['providers']['anthropic-promo']['body']['max_tokens'] = 2048
    no_steps_after, no_steps_edits = splice(original, legacy, True)
    legacy['agents']['api-promo-review']['steps'] = 1
    # Insertion formatting includes object key order: the legacy field preceded
    # system/permissions. Rebuild that exact historical agent order.
    agent = legacy['agents']['api-promo-review']
    legacy['agents']['api-promo-review'] = {k: agent[k] for k in
        ('description', 'mode', 'steps', 'system', 'permissions')}
    old_after, old_edits = splice(original, legacy, True)
    if not any(sha(text) == item['after'] and edits == [tuple(e) for e in item['edits']]
               for text, edits in ((old_after, old_edits), (no_steps_after, no_steps_edits))):
        raise ValueError('not the exact owned 2048 installation')
    new['files'][0] = {**item, 'after': sha(after), 'edits': edits}
    # JSON normalizes tuples, including for comparison with a recovered journal.
    new = json.loads(json.dumps(new))
    if recovery and (recovery != {'old': old, 'new': new} or receipt not in (old, new)):
        raise ValueError('amendment journal/receipt mismatch')
    if not apply:
        return {'dry_run': True, 'amendment': 'owned 2048→8192 cap; omit steps',
                'resume': recovery is not None, 'routes_and_money_unchanged': True}
    if not recovery:
        atomic(pending, json.dumps({'old': old, 'new': new}), 0o600)
    # Recheck both files and receipt immediately before writes. No blind rollback.
    if (read(config) != current or read(root / 'routes.json') != route_text
            or private(journal) != receipt
            or stat.S_IMODE(config.stat().st_mode) != item['mode']
            or stat.S_IMODE((root / 'routes.json').stat().st_mode) != routes['mode']):
        raise ValueError('state changed; retained amendment journal for review')
    if sha(current) != new['files'][0]['after']:
        atomic(config, after, item['mode'])
    atomic(journal, json.dumps(new), 0o600)
    pending.unlink()
    directory = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'amended': True, 'routes_and_money_unchanged': True}


def rollback(root):
    root = Path(root).absolute()
    with (root / '.promo-install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (root / 'promo-amend.json').exists() or (root / 'promo-amend.json').is_symlink():
            raise ValueError('pending amendment; review/resume before rollback')
        journal = root / 'promo-install.json'
        manifest = json.loads(read(journal))
        outputs = []
        for item in manifest['files']:
            path = Path(item['path'])
            current = read(path) if path.exists() else '{}\n'
            if sha(current) == item['before']:
                continue  # interrupted install or already rolled back
            if sha(current) != item['after'] or stat.S_IMODE(path.stat().st_mode) != item['mode']:
                raise ValueError('postimage/mode changed; no rollback writes performed')
            adjusted, offset = [], 0
            for pos, value in item['edits']:
                adjusted.append((pos + offset, value))
                offset += len(value)
            for pos, value in reversed(adjusted):
                if current[pos:pos+len(value)] != value:
                    raise ValueError('scoped rollback mismatch')
                current = current[:pos] + current[pos+len(value):]
            if sha(current) != item['before']:
                raise ValueError('rollback preimage mismatch')
            outputs.append((path, current, item))
        for path, value, item in outputs:
            if item['existed']:
                atomic(path, value, item['mode'])
            else:
                path.unlink()
        # Counter and authority are never deleted. Disable further preparation/sending.
        credit = Credit(root / 'promo.sqlite3')
        try:
            credit.db.execute('DELETE FROM authority')
        finally:
            credit.close()
    return {'rolled_back': True, 'money_records_retained': True}
