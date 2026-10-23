#!/usr/bin/env python3
"""Replace only startup/checkpoint/delivery authority, archiving every existing byte."""
import argparse
from pathlib import Path

from install_paths import DestinationRoot
from render import render


def replacements(home, brief):
    targets = {brief / 'AGENTS.md': render('kits/chief/memory/AGENTS.md', str(brief)),
               home / '.config/opencode/commands/checkpoint.md':
               render('workflows/checkpoint/hosts/opencode-command.md', str(brief))}
    for prefix in ('.claude', '.codex'):
        targets[home / prefix / 'skills/checkpoint/SKILL.md'] = render(
            'workflows/checkpoint/hosts/skill.md', str(brief))
    for prefix in ('.config/opencode', '.claude', '.codex'):
        targets[home / prefix / 'skills/delivery-outlook/SKILL.md'] = render(
            'kits/shared/skills/delivery-outlook.md', str(brief))
    return targets


def deploy(home, brief, dry=False):
    home, brief = Path(home).resolve(), Path(brief).resolve()
    archive = brief / 'archive/reset-20261022-authority/installed'
    prepared = []
    for target, text in replacements(home, brief).items():
        # Existing installs only. Do not create new host exports by implication.
        if not target.exists():
            continue
        DestinationRoot(home).validate_all([target])
        old = target.read_text()
        if 'managed by chief-of-staff/install.sh' not in old:
            raise ValueError('unmanaged authority target: ' + str(target))
        if old == text:
            continue
        backup = archive / target.relative_to(home)
        DestinationRoot(brief).validate_all([backup])
        if backup.exists() and backup.read_text() != old:
            raise ValueError('archive collision: ' + str(backup))
        prepared.append((target, old, text, backup))
    for target, old, text, backup in prepared:
        if dry:
            print('would preserve and update', target)
            continue
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with backup.open('x') as f:
                f.write(old)
        if backup.read_text() != old or target.read_text() != old:
            raise ValueError('archive/concurrent target mismatch')
        target.write_text(text)
        if target.read_text() != text:
            raise ValueError('readback mismatch')
        print('preserved and updated', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--brief', type=Path, default=Path.home() / '.chief-of-staff')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    deploy(args.home, args.brief, args.dry_run)
