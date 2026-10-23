#!/usr/bin/env python3
"""Build an absent-only isolated role tree; no runtime registration or config edits.

Native reset-* procedures are explicit-load only and omitted from automatic catalogs.
For live installation, inventory actual Location startup/catalog instructions first.
"""
import argparse
import json
from pathlib import Path

from install_paths import DestinationRoot
from render import render
from lean_roles import budget, procedures, render_role

ROOT = Path(__file__).resolve().parents[1]

def stage(output, chief_location, lead_location):
    output = Path(output).resolve()
    locations = {'chief': str(Path(chief_location).resolve()), 'lead': str(Path(lead_location).resolve())}
    roles = {r: render_role('hosts/opencode.md' if r == 'chief' else 'hosts/opencode-lead.md',
                            r, locations['chief']) for r in locations}
    bootstrap = render('kits/chief/memory/AGENTS.md', locations['chief'])
    chief_prose = roles['chief'].split('\n---\n', 1)[1] + '\n' + bootstrap
    if len(chief_prose.splitlines()) > 150 or len(chief_prose.split()) > 1600:
        raise ValueError('chief core plus bootstrap exceeds budget')
    files = {output / 'locations.json': json.dumps(locations, indent=2) + '\n',
             output / 'chief/AGENTS.md': bootstrap}
    for role, text in roles.items():
        files[output / role / f'.opencode/agents/{role}-reset-lean-20261022.md'] = text
        for ident, text in procedures(locations['chief']).items():
            files[output / role / f'.opencode/skills/{ident}/SKILL.md'] = text
    DestinationRoot(output).validate_all(files)
    if any(p.exists() or p.is_symlink() for p in files):
        raise ValueError('stage collision; retained, never overwritten')
    for target, text in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as f:
            f.write(text)
    print('staged only:', output)
    for role, text in roles.items():
        print(role, budget(role, text.split('\n---\n', 1)[1], locations['chief'],
                           header_prose='description: ' + role.capitalize() + '.'))
    print('Source stage only; registered pilot and actual Location context require separate readback.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--chief-location', required=True)
    parser.add_argument('--lead-location', required=True)
    args = parser.parse_args()
    stage(args.output, args.chief_location, args.lead_location)
