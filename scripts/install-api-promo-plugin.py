"""Parent-reviewed scoped plugin Python install; dry-run by default."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runway.promo_plugin_install import deploy

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(deploy(Path(__file__).resolve().parents[1], args.dist,
                                args.apply, args.rollback)))
    except Exception as exc:
        print(json.dumps({'error': 'Scoped deployment refused; review preimages/receipt',
                          'error_type': type(exc).__name__}))
        sys.exit(1)
