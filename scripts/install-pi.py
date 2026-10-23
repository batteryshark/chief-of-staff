#!/usr/bin/env python3
"""Fixed Pi resource lifecycle. No package installation, discovery or host launch."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from install_paths import DestinationRoot
from courtesy_owned import OwnedSkills, unique_object
from pi_render import compose


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def main(mode, capabilities):
    if mode not in ('install', 'uninstall', 'print', 'dry'):
        raise ValueError('invalid Pi mode')
    root = DestinationRoot(os.environ['HOME'])
    home = root.path
    if os.environ.get('PI_CODING_AGENT_DIR'):
        raise ValueError('Pi preset requires default ~/.pi/agent; unset PI_CODING_AGENT_DIR')
    selected = Path(os.environ.get('CHIEF_BRIEF_DIR', str(home / '.chief-of-staff')))
    if not selected.is_absolute() or '..' in selected.parts:
        raise ValueError('Pi brief must be absolute and inside HOME without ..')
    root.validate_all([selected / 'brief.md'])  # Never follow a child alias.
    brief = selected
    outputs, courtesy_path, courtesy_text = compose(home, brief, capabilities)
    outputs = {p: t.encode() for p, t in outputs.items()}
    inventory = home / '.config/chief-of-staff/pi-install.json'
    seeds = {brief / n: text.encode() for n, text in {
        'brief.md': '# Running brief\n\n## Priorities\n\n## Projects\n\n## Decisions\n\n## Parked\n',
        'open.md': '# Open items\n', 'principal.md': '# Standing permissions and preferences\n'}.items()}
    root.validate_all([*outputs, courtesy_path, inventory, *seeds])
    for p in [*outputs, courtesy_path, inventory, *seeds]:
        if p.exists() and not p.is_file():
            raise ValueError('Pi target must be an ordinary file: ' + str(p))
    owned = None
    if inventory.exists():
        owned = json.loads(inventory.read_text(), object_pairs_hook=unique_object)
        if (type(owned) is not dict or set(owned) != {'version', 'owner', 'owned'}
                or type(owned['version']) is not int or owned['version'] != 1
                or owned['owner'] != 'pi-preset' or type(owned['owned']) is not dict
                or not set(owned['owned']) <= {str(p.relative_to(home)) for p in outputs}
                or ({str(p.relative_to(home)) for p in outputs} - set(owned['owned'])) - {
                    f'.pi/agent/skills/{name}/SKILL.md' for name in ('delivery-outlook', 'comparative-review')}
                or any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}', v)
                       for v in owned['owned'].values())):
            raise ValueError('invalid Pi ownership inventory')
    for p in outputs:
        if p.exists():
            key = str(p.relative_to(home))
            if not owned or key not in owned['owned'] or digest(p.read_bytes()) != owned['owned'][key]:
                raise ValueError('unowned or modified Pi resource: ' + str(p))
        elif owned and str(p.relative_to(home)) in owned['owned']:
            raise ValueError('missing owned Pi resource; reconcile inventory: ' + str(p))
    # Separate immutable courtesy receipts retain the existing inode/hash guards.
    courtesy = OwnedSkills(home, {courtesy_path: courtesy_text}, owner='pi-preset')
    if mode == 'print':
        for p, data in outputs.items():
            print(f'=== {p}\n{data.decode()}')
        print(f'=== {courtesy_path}\n{courtesy_text}')
        return
    if mode == 'dry':
        for p in [*outputs, courtesy_path]:
            print('would write ' + str(p))
        for p in seeds:
            if not p.exists():
                print('would seed ' + str(p))
        return
    if mode == 'uninstall':
        courtesy.uninstall()
        if owned:
            for p in outputs:
                if str(p.relative_to(home)) in owned['owned']:
                    p.unlink()
            inventory.unlink()
        return  # Never prune user directories or remove seeds/settings/packages.
    courtesy.install()
    for p, data in outputs.items():
        if not p.exists() or p.read_bytes() != data:
            write(p, data)
    write(inventory, (json.dumps({'version': 1, 'owner': 'pi-preset',
          'owned': {str(p.relative_to(home)): digest(d) for p, d in outputs.items()}},
          indent=2) + '\n').encode())
    for p, data in seeds.items():
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as f:
                f.write(data)


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2:])
    except (ValueError, KeyError, OSError, TypeError) as e:
        sys.exit(f'install.sh: {e}')
