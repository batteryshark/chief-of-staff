#!/usr/bin/env python3
"""Chief-only bridge: explicit prepare, plan, activate, rollback; finite check."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from chief_bridge import (LOCK, apply_plan, bridge_plan, check_update, create, encoded,
                          lockfile, prepare, route_plan, runtime_receipt)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'check', 'plan', 'activate', 'rollback', 'routes-plan', 'routes-apply'])
    p.add_argument('--managed', type=Path, default=Path.home() / '.local/share/chief-of-staff/bridge')
    p.add_argument('--config', type=Path)
    p.add_argument('--source-repo', type=Path, help='owned clean local source at exact production lock (initial unpublished rollout)')
    p.add_argument('--bun', default=shutil.which('bun'))
    p.add_argument('--plan', type=Path)
    p.add_argument('--receipt', type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--parent-release-quiet-window', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    lock = lockfile()
    if args.dry_run:
        print(json.dumps({'action': args.action, 'lock': lock, 'effects': 'none; no fetch/build/config writes'}))
        return
    if args.action in ('prepare', 'check'):
        if args.action == 'prepare' and not args.bun:
            p.error('existing Bun required: --bun /path/to/cached/bun (no automatic install)')
        if args.action == 'check':
            result = check_update(args.managed, lock, args.bun, source_repo=args.source_repo)
        else:
            result = prepare(args.managed, lock, args.bun, args.source_repo)
            result['runtime'] = runtime_receipt(Path(result['directory']))
    elif args.action in ('plan', 'routes-plan'):
        if not args.config or not args.plan:
            p.error('--config and absent --plan required')
        result = (route_plan(args.config) if args.action == 'routes-plan' else
                  bridge_plan(args.config, args.managed / 'revisions' / lock['commit'], lock, args.previous))
        create(args.plan, encoded(result))
        result = {'status': 'planned-not-applied', 'plan': str(args.plan), 'kind': result['kind'],
                  'before_sha256': result['before_sha256'], 'after_sha256': result['after_sha256']}
    else:
        if not args.plan or not args.receipt:
            p.error('--plan and absent --receipt required')
        # Prevent accidentally using the wrong deployment lane.
        from chief_bridge import load
        kind = load(args.plan)['kind']
        if (args.action == 'routes-apply') != (kind == 'routes') and args.action != 'rollback':
            p.error('plan kind does not match action')
        apply_plan(args.plan, args.receipt, quiet=args.parent_release_quiet_window, rollback=args.action == 'rollback')
        result = {'status': args.action, 'receipt': str(args.receipt)}
    print(json.dumps(result, indent=2))
    if result.get('status') == 'stopped':
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f'chief-bridge: STOP: {exc}')
