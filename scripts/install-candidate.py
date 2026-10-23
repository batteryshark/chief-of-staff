#!/usr/bin/env python3
"""Absent-only local proof clone. No seeds, registry, global files or removal."""
import json
from pathlib import Path
import re
import sys

from install_paths import DestinationRoot
from render import render
from access_policy import agent_parts
from role_contract import permissions


def candidate(config):
    if not isinstance(config, dict) or set(config) != {'role', 'name', 'location', 'brief'}:
        raise ValueError('candidate requires role, name, location and brief')
    role, name = config['role'], config['name']
    if role not in ('chief', 'lead') or not isinstance(name, str) or not re.fullmatch(role + r'-edit-proof-[a-z0-9-]{1,32}', name):
        raise ValueError('unique role-edit-proof name required')
    for key in ('location', 'brief'):
        value = config[key]
        if not isinstance(value, str) or not Path(value).is_absolute() or str(Path(value).resolve()) != value:
            raise ValueError('canonical absolute location and brief required')
    location, brief = Path(config['location']), Path(config['brief'])
    if not location.is_dir() or not brief.is_dir():
        raise ValueError('existing location and brief required')
    if role == 'chief' and location != brief:
        raise ValueError('chief relative proof grant requires Location == brief')
    target = location / '.opencode/agents' / (name + '.md')
    DestinationRoot(location).validate_all([target])
    template = 'hosts/opencode.md' if role == 'chief' else 'hosts/opencode-lead.md'
    text = render(template, str(brief))
    header, body, existing, fields, match = agent_parts(text)
    rules = permissions(role, str(Path.home().resolve()), str(brief), str(location))
    rules += [r for r in existing if r['effect'] == 'deny' and r not in rules]
    if role == 'chief':
        rules.append(dict(action='edit', resource='_permission-proof-chief.md', effect='allow'))
    # Keep the source role's edit/inbox boundaries; prevent proof turns from
    # dispatching workers or using shell as a write bypass. No goal-mode runner.
    for action in ('shell', 'subagent', 'execute', 'openchamber*', 'a2a*', 'runway'):
        rules.append(dict(action=action, resource='*', effect='deny'))
    if fields is not None:
        fields.update(permissions=rules, steps=10)
        header = json.dumps(fields)
    else:
        if match is None:
            raise ValueError('source role has no supported permissions')
        header = ((header + '\n')[:match.start()] + 'permissions: ' + json.dumps(rules) + '\n' +
                  (header + '\n')[match.end():]).rstrip('\n') + '\nsteps: 10'
    marker = f'<!-- managed by chief-of-staff/install.sh; isolated candidate {name} -->'
    guard = ('# Bounded permission probe ONLY\n\n'
             'This is an isolated role clone, not an active chief or lead. Follow only the '
             'explicit fixture prompt. Do not read live state, update pointers/logs, delegate, '
             'schedule, notify, or start autonomous workflows. Use native patch/edit only for '
             'the named fixtures; a denial is final. Stop after the requested observations.\n\n')
    return target, '---\n' + header + '\n---\n' + marker + '\n\n' + guard + body + '\n'


def main(config_path, mode):
    if mode not in ('install', 'dry', 'print'):
        raise ValueError('candidates are retained; uninstall is not supported')
    target, text = candidate(json.loads(Path(config_path).read_text()))
    # Even our own marker is not authority to overwrite a retained candidate.
    if target.exists() or target.is_symlink():
        raise ValueError('candidate collision (retained, never overwritten): ' + str(target))
    if mode == 'print':
        print(text, end='')
    elif mode == 'dry':
        print('would create only ' + str(target))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as f:
            f.write(text)
        print('created ' + str(target))


if __name__ == '__main__':
    try:
        main(*sys.argv[1:])
    except (ValueError, TypeError, KeyError, OSError) as e:
        sys.exit('install.sh: ' + str(e))
