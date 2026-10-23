#!/usr/bin/env python3
"""Install one lead's permission-only Location binding using trusted Knowledge discovery.

No roster enrollment or session/model/goal operation. Global prompts are a separate migration.
Internal own-file permissions are generic in the global role. This optional binding
adds exact absolute aliases and current Knowledge plans; rerun after creating a Plan.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import tempfile

from install_paths import DestinationRoot
from role_contract import canonical, knowledge_plans, project_config


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
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.location, args.brief, args.dry_run), indent=2))
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error))
