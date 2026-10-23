#!/usr/bin/env python3
"""Normal exact-owned shim removal. Historical reports/receipts and foreign files stay."""
import argparse
import json
from pathlib import Path
from role_cleanup import remove_shims

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(); home = Path.home(); owned = {}
    for receipt in (home / '.chief-of-staff/archive').glob('reset-*/install-*.json'):
        for name, digest in json.loads(receipt.read_text()).get('after', {}).items():
            if isinstance(digest, str) and len(digest) == 64:
                owned.setdefault(name, set()).add(digest)
    try:
        print(json.dumps({'status':'removed' if args.apply else 'would-remove',
                          'files':remove_shims(home, owned, dry=not args.apply)}, indent=2))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
