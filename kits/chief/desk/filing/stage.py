"""Absent-only, explicit local staging. Never installs an agent or enables ingress."""
import argparse
import json
import os
from pathlib import Path
import stat


FILES = ('receiver.py', 'questions_policy.py', 'stage.py', 'instructions.md')


def check(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    check(isinstance(value, str) and value.startswith('/'), 'absolute path required')
    p = Path(value)
    check(str(p) == value and p.resolve(strict=True) == p, 'existing canonical path required')
    return p


def validate_config(c):
    check(set(c) == {'version', 'mode', 'chief_home', 'chief_pointer', 'open_source', 'chief', 'receiver_id', 'projects'}, 'control schema')
    check(type(c['version']) is int and c['version'] == 1 and c['mode'] in ('DISABLED', 'LIVE', 'PAUSED'), 'version/mode')
    home = canonical(c['chief_home'])
    check(home.is_dir(), 'chief home directory')
    for key in ('chief_pointer', 'open_source'):
        p = canonical(c[key])
        check(p.is_relative_to(home) and p.is_file(), 'selected chief source outside home')
    chief = c['chief']
    check(set(chief) == {'session_id', 'directory'} and isinstance(chief['session_id'], str) and chief['session_id'], 'chief route schema')
    check(canonical(chief['directory']).is_dir(), 'chief route directory')
    check(isinstance(c['receiver_id'], str) and c['receiver_id'] and c['receiver_id'] != chief['session_id'], 'actual receiver distinct from real chief')
    check(isinstance(c['projects'], dict) and 1 <= len(c['projects']) <= 64, 'registry count')
    ids = set()
    for key, reg in c['projects'].items():
        check(canonical(key).is_dir(), 'registered project directory')
        check(set(reg) in ({'title', 'lead_session', 'enabled'}, {'title', 'lead_session', 'enabled', 'handover'}), 'registry schema')
        check(isinstance(reg['enabled'], bool), 'enabled bool')
        check(isinstance(reg['title'], str) and 1 <= len(reg['title']) <= 120 and '\n' not in reg['title'], 'title')
        check(isinstance(reg['lead_session'], str) and reg['lead_session'], 'actual current lead required')
        if 'handover' in reg:
            h = reg['handover']
            check(set(h) == {'note_id', 'body', 'body_hash', 'authorization'}, 'exact handover schema')
            import hashlib
            check(isinstance(h['note_id'], str) and h['note_id'] and h['note_id'] not in ids, 'unique handover ID')
            ids.add(h['note_id'])
            check(isinstance(h['body'], str) and hashlib.sha256(h['body'].encode()).hexdigest() == h['body_hash'], 'handover body/hash')
            check(isinstance(h['authorization'], str) and h['authorization'], 'explicit trusted handover required')


def safe_chain(path):
    """Trust OS-owned ancestors; reject links and writable ancestors throughout.

    Not protection against a malicious same-UID process changing paths mid-call.
    """
    for p in reversed((path, *path.parents)):
        s = p.lstat()
        check(stat.S_ISDIR(s.st_mode) and s.st_uid in (0, os.getuid()) and not s.st_mode & 0o022, 'unsafe ancestor: ' + str(p))


def stage(home, destination, config):
    home = canonical(str(home))
    destination = Path(destination)
    check(destination.is_absolute() and str(destination) == str(home / destination.name), 'destination must be a direct new child of selected HOME')
    safe_chain(home)
    check(home.stat().st_uid == os.getuid(), 'HOME owner')
    check(not os.path.lexists(destination), 'destination already exists; no retry/overwrite')
    validate_config(config)
    check(config['mode'] == 'DISABLED' and all(not r['enabled'] for r in config['projects'].values()), 'staging must be disabled')
    source = Path(__file__).resolve().parent
    payloads = {}
    for name in FILES:
        p = source / name
        s = p.lstat()
        check(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == os.getuid() and not s.st_mode & 0o022, 'unsafe source')
        payloads[name] = p.read_bytes()
    payloads['control.json'] = json.dumps(config, indent=2).encode()
    payloads['state.json'] = json.dumps({'version': 1, 'admissions': {}, 'receipts': {}, 'projects': {}, 'digests': {}, 'pending': None, 'queue': []}).encode()
    payloads['writer.lock'] = b''
    check(len(payloads) == 7, 'staging file count')
    # Every target is preflighted before mutation. No reuse/repair/partial retry.
    os.mkdir(destination, 0o700)
    os.chmod(destination, 0o700)
    for name, content in payloads.items():
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    fd = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    from receiver import loads, metadata
    config_path = canonical(args.config)
    safe_chain(config_path.parent)
    metadata(config_path)
    c = loads(config_path.read_text())
    print(stage(args.home, args.destination, c))
