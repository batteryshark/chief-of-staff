#!/usr/bin/env python3
"""Absent-only scoped lean bundle with archive-only rollback; no config or session switch."""
import json
from pathlib import Path
import re
import sys

from install_paths import DestinationRoot
from lean_roles import budget, installed_startup, procedures, render_role


def plan(config):
    if not isinstance(config, dict) or set(config) - {'role', 'name', 'location', 'brief', 'heartbeat'}:
        raise ValueError('pilot requires role/name/location/brief; optional disabled heartbeat')
    role, name = config['role'], config['name']
    if role not in ('chief', 'lead') or not re.fullmatch(role + r'-reset-staged-[a-z0-9-]{1,32}', name):
        raise ValueError('unique role-reset-staged name required')
    for key in ('location', 'brief'):
        value = config[key]
        if not isinstance(value, str) or not Path(value).is_absolute() or str(Path(value).resolve()) != value:
            raise ValueError('canonical absolute location/brief required')
        if not Path(value).is_dir():
            raise ValueError('existing Location/brief required')
    location = Path(config['location'])
    if role == 'chief' and config['location'] != config['brief']:
        raise ValueError('chief Location must equal declared memory brief')
    template = 'hosts/opencode.md' if role == 'chief' else 'hosts/opencode-lead.md'
    text = render_role(template, role, config['brief'])
    budget(role, text.split('\n---\n', 1)[1], config['brief'],
           startup=installed_startup(location), header_prose='description: ' + role.capitalize() + '.')
    files = {location / f'.opencode/agents/{name}.md': text}
    for ident, resource in procedures(config['brief']).items():
        files[location / f'.opencode/skills/{ident}/SKILL.md'] = resource
    heartbeat = config.get('heartbeat')
    if heartbeat is not None:
        if (set(heartbeat) != {'source', 'pilotSessionID', 'enabled'} or heartbeat['enabled'] is not False
                or not re.fullmatch(r'ses_[A-Za-z0-9]+', heartbeat['pilotSessionID'])
                or not Path(heartbeat['source']).is_absolute()):
            raise ValueError('heartbeat seam is disabled-first, one source and pilot session only')
        options = {'enabled': False, 'pilotSessionID': heartbeat['pilotSessionID'],
                   'allowedLocation': str(location), 'chiefPointer': str(Path(config['brief']) / 'chief.json')}
        # Deliberately no import/copy of the author's changing implementation.
        # Final entrypoint + fresh-pointer authorization contract is a release seam.
        wrapper = ('// managed by chief-of-staff/install.sh; disabled scoped heartbeat seam\n'
                   f'const source = {json.dumps(Path(heartbeat["source"]).as_uri())};\n'
                   f'const options = {json.dumps(options)};\n'
                   'export default { id: "' + name + '-heartbeat", async setup() {\n'
                   '  if (!options.enabled) return;\n'
                   '  throw new Error("Reviewed heartbeat entrypoint, fresh chief pointer, reply/close/wait/Nod contract required: " + source);\n'
                   '} };\n')
        files[location / f'.opencode/plugins/{name}-heartbeat.js'] = wrapper
    journal = location / f'.opencode/reset-install/{name}.json'
    DestinationRoot(location).validate_all([*files, journal])
    return location, files, journal


def run(config, mode):
    if mode not in ('install', 'dry', 'print', 'uninstall'):
        raise ValueError('unsupported pilot mode')
    location, files, journal = plan(config)
    if mode == 'print':
        for target, text in files.items():
            print('=== ' + str(target) + '\n' + text)
        return
    if mode == 'uninstall':
        receipt = json.loads(journal.read_text())
        if receipt['config'] != config or receipt['state'] != 'installed':
            raise ValueError('pilot receipt differs or already archived')
        expected = {Path(p): text for p, text in receipt['files'].items()}
        if any(not p.is_file() or p.read_text() != text for p, text in expected.items()):
            raise ValueError('pilot changed since install; preserve and reconcile, not overwrite')
        archive = journal.parent / (config['name'] + '-archived')
        targets = [archive / p.relative_to(location) for p in expected]
        DestinationRoot(location).validate_all([*expected, *targets])
        if archive.exists():
            raise ValueError('archive collision')
        for target, destination in zip(expected, targets):
            destination.parent.mkdir(parents=True, exist_ok=True)
            target.rename(destination)
            assert destination.read_text() == expected[target]
        receipt['state'] = 'archived'
        journal.write_text(json.dumps(receipt, indent=2) + '\n')
        print('archived owned pilot bundle: ' + str(archive))
        return
    if journal.exists():
        receipt = json.loads(journal.read_text())
        if receipt.get('state') == 'installed' and receipt.get('config') == config and receipt.get('files') == {str(p): t for p, t in files.items()} and all(p.is_file() and p.read_text() == t for p, t in files.items()):
            print('same scoped pilot')
            return
        raise ValueError('retained pilot receipt; choose a fresh name or reconcile')
    if any(p.exists() or p.is_symlink() for p in files):
        raise ValueError('pilot collision; never overwrite existing roles/resources/plugins')
    if mode == 'dry':
        print('\n'.join('would create ' + str(p) for p in files))
        return
    for target, text in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as f:
            f.write(text)
        assert target.read_text() == text
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open('x') as f:
        json.dump({'config': config, 'state': 'installed', 'files': {str(p): t for p, t in files.items()}}, f, indent=2)
        f.write('\n')
    role_text = next(t for p, t in files.items() if p.parent.name == 'agents')
    counts = budget(config['role'], role_text.split('\n---\n', 1)[1], config['brief'],
                    startup=installed_startup(location),
                    header_prose='description: ' + config['role'].capitalize() + '.')
    print(json.dumps({'installed': config['name'], 'location': str(location), 'counts': counts,
                      'activation': 'registered only; no session or global role switched'}))


if __name__ == '__main__':
    raise SystemExit('Retired staged-agent installer; use install.sh --role-fixture with normal role names.')
    try:
        run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    except (ValueError, KeyError, OSError, TypeError) as error:
        raise SystemExit(str(error))
