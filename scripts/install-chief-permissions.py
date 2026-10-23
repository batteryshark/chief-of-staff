#!/usr/bin/env python3
"""Permission-only managed chief deployment. No prompt, lead, seed or config writes."""
import argparse
import json
import re
from pathlib import Path
import tempfile

from install_paths import DestinationRoot
from render import render
from access_policy import agent_parts


def repaired(current, brief):
    if 'managed by chief-of-staff/install.sh' not in current or not current.startswith('---\n'):
        raise ValueError('existing managed chief required')
    header, body, existing, fields, match = agent_parts(current)
    if not existing:
        raise ValueError('existing permission rules required')
    source = agent_parts(render('hosts/opencode.md', brief))[2]
    missing = [rule for rule in source if rule['action'] == 'edit' and rule['effect'] == 'allow' and rule not in existing]
    clamps = [rule for rule in source if rule['action'] == 'edit' and rule['effect'] == 'deny'
              and rule['resource'] != '*' and rule not in existing]
    if not missing and not clamps:
        return current
    # Add generated capabilities before custom edit denials; preserve their authority.
    boundary = next((i for i, rule in enumerate(existing) if rule['action'] == 'edit' and
                     rule['effect'] == 'deny' and not (i == 0 and rule['resource'] == '*')), len(existing))
    rules = existing[:boundary] + missing + existing[boundary:] + clamps
    if fields is not None:
        fields['permissions'] = rules
        header = json.dumps(fields, separators=(',', ':'))
    else:
        if match is None:
            raise ValueError('unsupported permission frontmatter')
        header = (header + '\n')[:match.start()] + 'permissions: ' + json.dumps(rules) + '\n' + (header + '\n')[match.end():]
    return '---\n' + header.rstrip('\n') + '\n---\n' + body


def deploy(brief, home, dry=False, revision=None, local=False):
    brief, home = Path(brief).resolve(), Path(home).resolve()
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', revision)):
        raise ValueError('revision must be a safe nonempty basename without separators or traversal')
    target = (brief / '.opencode/agents/chief-of-staff.md') if local else home / '.config/opencode/agents/chief-of-staff.md'
    folder = 'reset-' + revision + '-permission' if revision is not None else 'reset-20261022-permission'
    backup = brief / 'archive' / folder / ('chief-of-staff.local.md' if local else 'chief-of-staff.md')
    DestinationRoot(home).validate_all([target])
    DestinationRoot(brief).validate_all([backup])
    before = target.read_text()
    if local and '; lean role' not in agent_parts(before)[1]:
        raise ValueError('fixed local target must be the managed canonical lean chief')
    after = repaired(before, str(brief))
    if before == after:
        return 'same ' + str(target)
    if backup.exists():
        raise ValueError('archive collision; retain and reconcile before another deployment')
    if dry:
        return f'would archive {target} to {backup}; update only edit permissions'
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open('x') as f:
        f.write(before)
    if backup.read_text() != before or target.read_text() != before:
        raise ValueError('archive or concurrent target changed; not deployed')
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as f:
        f.write(after)
        temporary = Path(f.name)
    temporary.chmod(target.stat().st_mode & 0o777)
    temporary.replace(target)
    if target.read_text() != after:
        raise ValueError('deployment readback mismatch')
    return 'updated only chief edit permissions; archive: ' + str(backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('brief')
    parser.add_argument('home')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--revision', help='explicit immutable backup revision; default collision behavior is unchanged')
    parser.add_argument('--local', action='store_true', help='repair only the fixed installed canonical local chief metadata')
    args = parser.parse_args()
    print(deploy(args.brief, args.home, args.dry_run, args.revision, args.local))
