"""Explicit parent-released install only; dry-run by default, no secret output."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runway.promo_install import install, rollback, amend

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, epilog='Fresh installs require local promo-policy.json, promo-opencode.json and promo-routes.json in --runway-home. See docs/LOCAL-SETUP.md; examples assert no grant or model availability.')
    p.add_argument('--config', type=Path)
    p.add_argument('--runway-home', type=Path, required=True)
    p.add_argument('--approval-file', type=Path)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--rollback', action='store_true')
    p.add_argument('--amend', action='store_true', help='exact owned 2048→8192/no-steps transition; dry-run default')
    a = p.parse_args()
    try:
        if a.amend and a.rollback:
            raise ValueError('choose amendment or rollback')
        if a.amend:
            if not a.config or a.approval_file:
                raise ValueError('amend requires config, not approval')
            result = amend(Path(__file__).resolve().parents[1], a.config, a.runway_home, a.apply)
        elif a.rollback:
            if not a.apply:
                raise ValueError('rollback requires --apply')
            result = rollback(a.runway_home)
        else:
            if not a.config or not a.approval_file:
                raise ValueError('explicit config and private approval file required')
            approval = json.loads(a.approval_file.read_text())
            result = install(Path(__file__).resolve().parents[1], a.config, a.runway_home, approval, a.apply)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'error': 'Promo install/amend/rollback refused; no secret details emitted',
                          'error_type': type(error).__name__}))
        raise SystemExit(1)
