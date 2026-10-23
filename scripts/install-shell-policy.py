#!/usr/bin/env python3
"""Scoped native shell-wrapper exclusion. No role/session/model/goal or plugin-source edits."""
import argparse
import json
import os
from pathlib import Path
import stat
import tempfile

from install_paths import DestinationRoot
from role_contract import canonical, shell_wrapper_policy


def install(location, dry=False):
    location = Path(canonical(str(location)))
    if not location.is_dir():
        raise ValueError('existing canonical Location required')
    target = location / '.opencode/opencode.json'
    DestinationRoot(location).validate_all([target])
    if (location / 'opencode.jsonc').exists() or target.with_suffix('.jsonc').exists():
        raise ValueError('existing JSONC requires preserving its source, not shadowing it')
    before = target.read_bytes() if target.exists() else None
    existing = json.loads(before) if before is not None else {}
    result = shell_wrapper_policy(existing, str(Path.home()))
    if result == existing:
        return {'status': 'same', 'target': str(target)}
    if dry:
        return {'status': 'would-update', 'target': str(target), 'addedPolicies': result['policies'][len(existing.get('policies', [])):]}
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if before is not None else 0o600
    fd, name = tempfile.mkstemp(prefix='.shell-policy-', dir=target.parent)
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
    return {'status': 'updated', 'target': str(target), 'scope': 'only local-foreground-shell-guard integration policies'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('location', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.location, args.dry_run), indent=2))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
