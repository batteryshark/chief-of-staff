"""Pinned API-only Python deployment. Never rebuild/reload JS or open runtime DBs."""
import fcntl
import json
import stat
from pathlib import Path

from .promo_install import atomic, read, sha

PREIMAGES = {
    'runway/cli.py': '1294ddc9acdb56bd35ac8e50dabaf414fbdc362fbe2ef092f65a7b201a1f0dbc',
    'WORKFLOW.md': '9fcf9697ef41bc763d36c00ee3e845f4fa8f8129bcb06148cbcac5855f5c9b41',
}


def cli_edits(source):
    text = (source / 'runway/cli.py').read_text()
    def section(start, end):
        return text[text.index(start):text.index(end, text.index(start))]
    return [
        ('', section('    # API-required work', "    if action == 'dispatch-get':"),
         "    action = req['action']\n"),
        ('', section("        promo_action =", '        registered = registration()'),
         '        req = json.load(sys.stdin)\n'),
        ('', section("        if req['action'] in ('status', 'usage')", '        print(result if'),
         '        result = handle(req, config, ledger, LocalAPI(args.tarmac), host)\n'),
        ("        print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__,\n",
         "        print(json.dumps({'error': 'Runway request failed; no automatic resend; check input, approval and attempt state',\n"
         "                          'error_type': type(exc).__name__,\n", ''),
    ]


def transform(text, edits, reverse=False):
    for old, new, anchor in reversed(edits) if reverse else edits:
        old, new = anchor + old, anchor + new
        if reverse:
            old, new = new, old
        if not old or text.count(old) != 1:
            raise ValueError('exact API CLI anchor mismatch')
        text = text.replace(old, new, 1)
    return text


def deploy(source, target, apply=False, rollback=False):
    source, target = Path(source).absolute(), Path(target).absolute()
    if any(p.is_symlink() for p in (target, *target.parents, target / 'runway')):
        raise ValueError('real dist directory required')
    if not target.is_dir() or not (target / 'runway').is_dir():
        raise ValueError('existing dist/runway required')
    journal = target / '.api-promo-python.json'
    lock = target / '.api-promo-python.lock'
    if not apply:
        return _deploy(source, target, journal, False, rollback)
    if lock.is_symlink():
        raise ValueError('symlink lock refused')
    with lock.open('a') as handle:
        lock.chmod(0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _deploy(source, target, journal, True, rollback)


def _deploy(source, target, journal, apply, rollback):
    edits = cli_edits(source)
    marker = '# API promotional candidate (separate from percent quotas)\n'
    workflow = (source / 'routing/WORKFLOW.md').read_text()
    appendix = '\n' + workflow[workflow.index(marker):]
    stored = None
    if journal.exists() or journal.is_symlink():
        stored = json.loads(read(journal))
        if stat.S_IMODE(journal.stat().st_mode) != 0o600:
            raise ValueError('private deployment journal required')
    if rollback and not stored:
        raise ValueError('deployment receipt required')
    if stored and stored['target'] != str(target):
        raise ValueError('deployment target mismatch')
    outputs, files, observed = {}, {}, {}
    # Validate EVERY pre/postimage and mode before any write. Journal permits
    # interrupted forward/rollback recovery, never overwriting third-party edits.
    for name in (*PREIMAGES, 'runway/promo.py', 'runway/promo_native.py'):
        path = target / name
        current = read(path) if path.exists() or path.is_symlink() else None
        mode = stat.S_IMODE(path.stat().st_mode) if current is not None else None
        observed[path] = (current, mode)
        prior = stored['files'][name] if stored else None
        if prior and (sha(current) if current is not None else None) not in (prior['before'], prior['after']):
            raise ValueError('deployment image changed')
        if current is not None and mode != 0o644:
            raise ValueError('deployment mode changed')
        if name == 'runway/cli.py':
            before = transform(current, edits, True) if prior and sha(current) == prior['after'] else current
            after = transform(before, edits)
        elif name == 'WORKFLOW.md':
            before = current[:-len(appendix)] if prior and sha(current) == prior['after'] and current.endswith(appendix) else current
            after = before + appendix
        else:
            before = None
            after = (source / name).read_text()
            if not prior and current is not None:
                raise ValueError('new module collision')
        entry = {'before': sha(before) if before is not None else None,
                 'after': sha(after), 'mode': 0o644}
        if name in PREIMAGES and entry['before'] != PREIMAGES[name]:
            raise ValueError('pinned installed preimage mismatch')
        if prior and prior != entry:
            raise ValueError('source/receipt mismatch')
        files[name] = entry
        outputs[path] = before if rollback else after
    receipt = {'target': str(target), 'files': files}
    if not apply:
        return {'dry_run': True, 'rollback': rollback, **receipt}
    if not stored:
        atomic(journal, json.dumps(receipt), 0o600)
    for path, (text, mode) in observed.items():
        now = read(path) if path.exists() or path.is_symlink() else None
        now_mode = stat.S_IMODE(path.stat().st_mode) if now is not None else None
        if (now, now_mode) != (text, mode):
            raise ValueError('deployment changed during validation; receipt retained')
    for path, text in outputs.items():
        if text is None:
            if path.exists():
                path.unlink()
        else:
            atomic(path, text, 0o644)
    if rollback:
        journal.unlink()
    return {'applied': True, 'rollback': rollback, **receipt}
