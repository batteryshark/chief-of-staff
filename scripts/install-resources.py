#!/usr/bin/env python3
"""Exact-owned default service guides, preflighted before legacy mutations."""
import hashlib
import json
from pathlib import Path
import re
import sys

from install_paths import DestinationRoot
from service_resources import resource_outputs


def main(home, mode, *hosts):
    root = DestinationRoot(home)
    outputs = resource_outputs(root.path, '<!-- managed by chief-of-staff service guides -->')
    inventory = root.path / '.kit-resources/inventory.json'
    root.validate_all([inventory, *outputs])
    previous = json.loads(inventory.read_text()) if inventory.exists() else None
    selected = set(hosts) & {'opencode', 'claude', 'codex', 'home'}
    relative = lambda p: str(p.relative_to(root.path))
    if previous is not None and (type(previous) is not dict or set(previous) != {'version', 'owned', 'hosts'}
            or type(previous['version']) is not int or previous['version'] != 1
            or type(previous['owned']) is not dict
            or set(previous['owned']) != {relative(p) for p in outputs}
            or any(type(h) is not str or not re.fullmatch('[0-9a-f]{64}', h) for h in previous['owned'].values())
            or type(previous['hosts']) is not list or not previous['hosts']
            or any(type(h) is not str or h not in ('opencode', 'claude', 'codex', 'home') for h in previous['hosts'])
            or len(set(previous['hosts'])) != len(previous['hosts'])):
        raise ValueError('invalid service guide inventory; preserve and reconcile')
    for p in outputs:
        if p.exists() and (not p.is_file() or not previous or
                hashlib.sha256(p.read_bytes()).hexdigest() != previous['owned'][relative(p)]):
            raise ValueError('unowned or modified service guide: ' + str(p))
    if mode == 'check':
        return
    if mode in ('print', 'dry'):
        for p, text in outputs.items():
            print('=== ' + str(p) + '\n' + text if mode == 'print' else 'would manage ' + str(p))
        return
    remaining = set(previous['hosts']) - selected if previous else set()
    if mode == 'uninstall' and not remaining:
        if previous:
            for p in outputs:
                if p.exists(): p.unlink()
            inventory.unlink()
        return
    if mode not in ('install', 'uninstall'):
        raise ValueError('invalid resource mode')
    from tempfile import NamedTemporaryFile
    def atomic(p, text):
        p.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode='w', dir=p.parent, delete=False) as f:
            temp = Path(f.name)
            f.write(text)
        try:
            temp.replace(p)
        finally:
            if temp.exists(): temp.unlink()
    if mode == 'install':
        for p, text in outputs.items():
            atomic(p, text)
    else:
        atomic(inventory, json.dumps({**previous, 'hosts': sorted(remaining)}, indent=2) + '\n')
        return
    atomic(inventory, json.dumps(dict(version=1, owned={relative(p): hashlib.sha256(t.encode()).hexdigest()
                                                     for p, t in outputs.items()},
                                     hosts=sorted(selected | (set(previous['hosts']) if previous else set()))), indent=2) + '\n')


if __name__ == '__main__':
    try: main(*sys.argv[1:])
    except (ValueError, KeyError, OSError, TypeError) as e: sys.exit('install.sh: ' + str(e))
