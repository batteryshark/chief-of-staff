"""PRIVATE stdin bridge, not installed on PATH or exposed in model catalogs.

The fixed JS host launcher owns access. No --verified option, auth discovery,
transport, shell execution, configuration administration or public CLI actions.
"""
import json
from pathlib import Path
import sys

# -I intentionally removes ambient/script import paths. Admit this fixed sibling
# directory only, not cwd, PYTHONPATH or user site packages.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desk_native import NativeStore, dispatch

MAX = 262144


def main():
    data = sys.stdin.buffer.read(MAX + 1)
    if len(data) > MAX:
        raise ValueError('host request exceeds bound')
    request = json.loads(data)
    if set(request) != {'home', 'op', 'args'}:
        raise ValueError('invalid host request')
    home = Path(request['home'])
    store = NativeStore(home)
    try:
        result = dispatch(store, request['op'], request['args'])
        output = json.dumps({'ok': True, 'data': result}, ensure_ascii=False)
        if len(output.encode()) > MAX:
            raise ValueError('host response exceeds bound; committed effects require reconciliation')
        sys.stdout.write(output)
    finally:
        store.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No input/trace/config paths/prose copied into model-visible error output.
        sys.stdout.write('{"ok":false,"error":"host operation failed; reconcile owned state"}')
        sys.exit(1)
