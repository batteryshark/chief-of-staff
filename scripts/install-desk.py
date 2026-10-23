#!/usr/bin/env python3
"""RETIRED / UNUSED desk installer, retained for history; do not activate.
Use lead-owned project status Notes and the ordinary install.sh instead.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from desk_store import atomic
from install_paths import DestinationRoot

SRC = Path(__file__).resolve().parent.parent


def install(root, home, mode, native_artifacts=False):
    raise ValueError('Desk installation is retired; use install.sh and lead-owned status Notes.')
    destination = DestinationRoot(root)
    home = Path(home)
    desk = home / 'desk'
    sources = {name: SRC / 'kits/chief/desk' / name for name in
               ('core.md', 'chief-instructions.md', 'luna.md', 'progress.template.html', 'checkpoint-lead.md')}
    sources.update({name: SRC / 'scripts' / name for name in ('desk.py', 'desk_store.py', 'install_paths.py')})
    outputs = {desk / name: source.read_text().replace('{{HOME}}', str(home)) for name, source in sources.items()}
    if native_artifacts:
        def native_source(source):
            metadata = source.lstat()
            if (source.resolve() != source or not source.is_file() or metadata.st_nlink != 1
                    or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022):
                raise ValueError(f'unsafe native artifact source: {source}')
            return source.read_text()

        # Staged artifacts ONLY. No plugin discovery entry, native host config,
        # agent/registry/pointer binding, permission/settings edits or activation.
        runtime = desk / 'native-runtime'
        for name in ('index.mjs', 'bridge.mjs', 'boundary.mjs', 'catalog.mjs',
                     'fixture-entry.mjs', 'fixture-config.mjs', 'fixture-package.json',
                     'fixture-assets.mjs', 'fixture-operator.mjs', 'fixture-observer.mjs',
                     'fixture-evidence.mjs'):
            outputs[runtime / 'hosts/desk-native' / name] = native_source(SRC / 'hosts/desk-native' / name)
        for name in ('desk_native.py', 'desk_native_bridge.py', 'desk_store.py', 'install_paths.py'):
            outputs[runtime / 'scripts' / name] = native_source(SRC / 'scripts' / name)
        outputs[runtime / 'scripts/progress.template.html'] = native_source(sources['progress.template.html'])
    outputs[desk / 'checkpoint-lead.md'] = (outputs[desk / 'checkpoint-lead.md']
        .replace('{{BRIEF_DIR}}', str(home))
        .replace('{{DESK_PROJECT}}', '<report project from LEAD.md>')
        .replace('{{LEAD_AGENT}}', '<current authorized lead agent>'))
    seeds = {home / 'desk.json': {'session': '', 'directory': str(home), 'updated': ''},
             desk / 'registry.json': {'version': 1, 'projects': {}, 'rules': {}},
             desk / 'routes.json': {'version': 1, 'projects': {}},
             desk / 'writer-protocol.json': {'version': 1, 'chief': False, 'desk': False}}
    manifest = desk / 'install-manifest.json'
    destination.validate_all([*outputs, *seeds, manifest])
    old = json.loads(manifest.read_text()) if manifest.exists() else {}
    for path in outputs:
        if path.exists() and old.get(str(path.relative_to(desk))) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f'unowned or locally changed desk file: {path}')
    for path, text in outputs.items():
        if mode == 'print':
            print(f'=== {path}\n{text}')
        elif mode == 'dry':
            print(f'would write {path}')
        elif mode == 'uninstall':
            if path.exists():
                path.unlink()
        elif mode == 'install':
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic(path, text)
        else:
            raise ValueError('invalid install mode')
    if mode == 'install':
        for path, value in seeds.items():
            if not path.exists():
                atomic(path, json.dumps(value, indent=2) + '\n')
        inventory = {**old, **{str(path.relative_to(desk)): hashlib.sha256(text.encode()).hexdigest()
                              for path, text in outputs.items()}}
        atomic(manifest, json.dumps(inventory, indent=2) + '\n')
    elif mode == 'uninstall' and manifest.exists():
        remaining = {key: value for key, value in old.items()
                     if desk / key not in outputs}
        if remaining:
            atomic(manifest, json.dumps(remaining, indent=2) + '\n')
        else:
            manifest.unlink()
    # Seeds, receipts, pointer, caches and all private state survive uninstall.


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='selected HOME; all destinations must be below it')
    p.add_argument('--home', required=True, help='canonical chief home below selected HOME')
    p.add_argument('--mode', choices=['install', 'uninstall', 'print', 'dry'], default='print')
    p.add_argument('--native-artifacts', action='store_true', help='stage inert optional host artifacts, never activate')
    args = p.parse_args()
    try:
        install(args.root, args.home, args.mode, args.native_artifacts)
    except (ValueError, OSError, KeyError, TypeError) as e:
        sys.exit(f'desk install: {e}')
