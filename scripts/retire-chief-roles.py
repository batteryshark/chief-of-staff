#!/usr/bin/env python3
"""Archive split-role exports; repair only the unsplit chief memory-authority section."""
import argparse
from pathlib import Path

from install_paths import DestinationRoot
from render import render


def memory_section(text):
    if '## Memory\n' not in text:
        start = text.index('## Durable record\n')
        end = text.index('## Principal attention', start)
        return start, end, text[start:end]
    start = text.index('## Memory\n')
    boundary = '## Models and usage\n' if '## Models and usage\n' in text[start:] else '## Principal attention'
    end = text.index(boundary, start)
    return start, end, text[start:end]


def repaired(old, rendered):
    start, end, _ = memory_section(old)
    section = memory_section(rendered)[2]
    return old[:start] + section + old[end:]


def deploy(home, brief, dry=False):
    home, brief = Path(home).resolve(), Path(brief).resolve()
    archive = brief / 'archive/reset-20261022-retirement/installed'
    unsplit = [('.config/opencode/agents/chief-of-staff.md', 'hosts/opencode.md'),
               ('.claude/agents/chief-of-staff.md', 'hosts/claude-agent.md'),
               ('.claude/output-styles/chief-of-staff.md', 'hosts/claude-output-style.md'),
               ('.codex/chief-of-staff.config.toml', 'hosts/codex.config.toml')]
    updates, retirements = [], []
    for relative, template in unsplit:
        target = home / relative
        if not target.is_file():
            raise ValueError('unsplit chief must remain installed: ' + str(target))
        DestinationRoot(home).validate_all([target])
        old = target.read_text()
        if 'managed by chief-of-staff/install.sh' not in old:
            raise ValueError('unmanaged chief export')
        after = repaired(old, render(template, str(brief)))
        updates.append((target, old, after, archive / relative))
    for prefix, suffix in (('.config/opencode/agents', '.md'), ('.claude/agents', '.md'),
                           ('.codex', '.config.toml')):
        for role in ('chief-ops', 'chief-front-door'):
            target = home / prefix / (role + suffix)
            if not target.exists():
                continue
            DestinationRoot(home).validate_all([target])
            old = target.read_text()
            if 'managed by chief-of-staff/install.sh' not in old:
                raise ValueError('unmanaged retired export')
            retirements.append((target, old, archive / target.relative_to(home)))
    backups = [item[3] for item in updates] + [item[2] for item in retirements]
    DestinationRoot(brief).validate_all(backups)
    if any(p.exists() or p.is_symlink() for p in backups):
        raise ValueError('retained archive collision; reconcile rather than overwrite')
    if dry:
        print(f'would preserve and repair {len(updates)} chief memory sections; archive {len(retirements)} split exports')
        return
    # Preserve every original before changing any active authority.
    for target, old, after, backup in updates:
        backup.parent.mkdir(parents=True, exist_ok=True)
        with backup.open('x') as f:
            f.write(old)
        assert backup.read_text() == old and target.read_text() == old
    for target, old, backup in retirements:
        backup.parent.mkdir(parents=True, exist_ok=True)
        # Move rather than delete; destination was preflighted absent.
        assert target.read_text() == old
        target.rename(backup)
        assert backup.read_text() == old
    for target, old, after, backup in updates:
        assert target.read_text() == old
        target.write_text(after)
        assert target.read_text() == after
    print(f'repaired {len(updates)} unsplit chief memory sections; archived {len(retirements)} split exports')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--brief', type=Path, default=Path.home() / '.chief-of-staff')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    deploy(args.home, args.brief, args.dry_run)
