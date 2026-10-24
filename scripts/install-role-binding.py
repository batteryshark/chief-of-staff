#!/usr/bin/env python3
"""Install one lead's permission-only Location binding using trusted Knowledge discovery.

No roster enrollment or session/model/goal operation. Global prompts are a separate migration.
Internal own-file permissions are generic in the global role. This optional binding
adds exact absolute aliases and current Knowledge plans. Native-plan-only migration
instead inserts the existing global grant into a reviewed legacy local overlay;
it neither enumerates plans nor regenerates the config or any role.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from install_paths import DestinationRoot
from role_contract import canonical, knowledge_plans, project_config, native_plan_overlay, rule


def plan_overlay_bytes(before, home):
    """Insert one JSON member; preserve every original byte and custom rule."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key; reconcile manually')
            result[key] = value
        return result
    decoder = json.JSONDecoder(object_pairs_hook=unique)
    text = before.decode('utf-8')
    existing = decoder.decode(text)
    desired = native_plan_overlay(existing, home)
    if desired == existing:
        return before
    grant = desired['agents']['lead']['permissions'][1]
    candidates = []
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            value, end = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if value != rule('edit', '*', 'deny'):
            continue
        candidate = text[:end] + ', ' + json.dumps(grant) + text[end:]
        if decoder.decode(candidate) == desired:
            candidates.append(candidate.encode('utf-8'))
    if len(candidates) != 1:
        raise ValueError('unique lead baseline insertion required')
    return candidates[0]


def install_native_plan(location, expected_sha256, dry=False):
    """Exact reviewed existing overlay only; no Knowledge/fleet discovery or roles."""
    location = Path(canonical(str(location)))
    target = location / '.opencode/opencode.json'
    DestinationRoot(location).validate_all([target])
    if (location / 'opencode.jsonc').exists() or target.with_suffix('.jsonc').exists():
        raise ValueError('JSONC requires source-preserving reconciliation')
    def evidence(path):
        canonical(str(path))
        s = path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid():
            raise ValueError('owned regular single-link config required')
        return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    mode=stat.S_IMODE(s.st_mode), uid=s.st_uid, gid=s.st_gid,
                    xattrs=subprocess.check_output(['xattr', '-lx', str(path)]),
                    acl=subprocess.check_output(['ls', '-lde', str(path)]).splitlines()[1:])
    original = evidence(target)
    if original['sha256'] != expected_sha256:
        raise ValueError('reviewed preimage hash required; config drifted')
    before = target.read_bytes()
    after = plan_overlay_bytes(before, str(Path.home()))
    post = dict(original, sha256=hashlib.sha256(after).hexdigest())
    details = dict(target=str(target), beforeSha256=original['sha256'], afterSha256=post['sha256'])
    if evidence(target) != original:
        raise ValueError('config changed during preparation')
    if before == after:
        return dict(details, status='same')
    if dry:
        return dict(details, status='would-update')
    fd, name = tempfile.mkstemp(prefix='.native-plan-', dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        subprocess.run(['/bin/cp', '-p', str(target), str(temporary)], check=True)
        with temporary.open('r+b') as out:
            out.write(after); out.truncate(); out.flush(); os.fsync(out.fileno())
        if evidence(temporary) != post or evidence(target) != original:
            raise ValueError('config or metadata drift; preserve/reconcile')
        os.replace(temporary, target)
        if evidence(target) != post:
            raise ValueError('installed readback mismatch; inspect before rollback')
    finally:
        if temporary.exists():
            temporary.unlink()
    return dict(details, status='updated')


def install(location, brief=None, dry=False):
    location = Path(canonical(str(location)))
    if not location.is_dir():
        raise ValueError('existing canonical Location required')
    home = str(Path.home())
    brief = canonical(str(brief or Path.home() / '.chief-of-staff'))
    plans = knowledge_plans(str(location), home)
    target = location / '.opencode/opencode.json'
    DestinationRoot(location).validate_all([target])
    if (location / 'opencode.jsonc').exists() or target.with_suffix('.jsonc').exists():
        raise ValueError('existing JSONC requires source-preserving reconciliation')
    before = target.read_bytes() if target.exists() else None
    existing = json.loads(before) if before is not None else {}
    result = project_config(existing, 'lead', home, brief, str(location), plans)
    details = {'location': str(location), 'target': str(target), 'exactKnowledgePlans': plans,
               'rosterEnrollmentChanged': False, 'sessionChanged': False}
    if result == existing:
        return dict(details, status='same')
    if dry:
        return dict(details, status='would-update')
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if before is not None else 0o600
    fd, name = tempfile.mkstemp(prefix='.role-binding-', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(result, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        temporary.chmod(mode)
        if (target.read_bytes() if target.exists() else None) != before:
            raise ValueError('config changed during preflight; preserve/retry')
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return dict(details, status='updated')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('location', type=Path)
    parser.add_argument('--brief', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--native-plan-only', action='store_true',
                        help='only amend an explicitly reviewed existing lead overlay; no Knowledge lookup')
    parser.add_argument('--expected-sha256', help='reviewed managed config preimage for --native-plan-only')
    args = parser.parse_args()
    try:
        if args.native_plan_only:
            if not args.expected_sha256 or args.brief:
                raise ValueError('--native-plan-only requires --expected-sha256 and no --brief')
            result = install_native_plan(args.location, args.expected_sha256, args.dry_run)
        else:
            if args.expected_sha256:
                raise ValueError('--expected-sha256 requires --native-plan-only')
            result = install(args.location, args.brief, args.dry_run)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error))
