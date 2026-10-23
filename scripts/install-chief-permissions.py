#!/usr/bin/env python3
"""Managed chief maintenance: permission-only by default; explicit body-only mode.

Body-only requires fixed global/canonical local ownership, expected file SHA and
an immutable revision backup. It preserves the complete frontmatter verbatim and
uses only the normal generator's body. Watched replacement can invalidate loaded
Locations; coordinate activation separately. No explicit reload or config writes.
"""
import argparse
import hashlib
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


def split_bytes(raw):
    if not raw.startswith(b'---\n'):
        raise ValueError('unsupported agent frontmatter')
    header, separator, body = raw.partition(b'\n---\n')
    if not separator:
        raise ValueError('unsupported agent frontmatter')
    return header + separator, body


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def deploy(brief, home, dry=False, revision=None, local=False, body_only=False, expected_sha256=None):
    if body_only:
        fixed_home = Path.home().resolve()
        if Path(home).resolve() != fixed_home or Path(brief) != fixed_home / '.chief-of-staff':
            raise ValueError('body-only requires the fixed home and canonical chief brief')
        DestinationRoot(fixed_home).validate_all([Path(brief)])
        if not Path(brief).is_dir():
            raise ValueError('existing canonical chief brief required')
        if revision is None:
            raise ValueError('body-only requires an explicit safe revision')
        if not isinstance(expected_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_sha256):
            raise ValueError('body-only requires expected current SHA256')
    elif expected_sha256 is not None:
        raise ValueError('expected SHA256 is supported only in body-only mode')
    brief, home = Path(brief).resolve(), Path(home).resolve()
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', revision)):
        raise ValueError('revision must be a safe nonempty basename without separators or traversal')
    target = (brief / '.opencode/agents/chief-of-staff.md') if local else home / '.config/opencode/agents/chief-of-staff.md'
    suffix = '-body' if body_only else '-permission'
    folder = 'reset-' + revision + suffix if revision is not None else 'reset-20261022-permission'
    backup = brief / 'archive' / folder / ('chief-of-staff.local.md' if local else 'chief-of-staff.md')
    DestinationRoot(home).validate_all([target])
    DestinationRoot(brief).validate_all([backup])
    before = target.read_bytes()
    if body_only:
        if sha(before) != expected_sha256:
            raise ValueError('expected current bytes differ; not deployed')
        header, old_body = split_bytes(before)
        marker = old_body.lstrip(b'\n').split(b'\n', 1)[0]
        lean = b'<!-- managed by chief-of-staff/install.sh; lean role -->'
        legacy = b'<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->'
        if marker not in (lean, legacy) or (local and marker != lean):
            raise ValueError('existing exact managed chief body required; local must be canonical lean chief')
        _, generated_body = split_bytes(render('hosts/opencode.md', str(brief)).encode('utf-8'))
        if not generated_body.startswith(lean + b'\n'):
            raise ValueError('normal generator did not produce the managed lean body')
        after = header + generated_body
        result = {'status': 'same' if before == after else 'would-update' if dry else 'updated',
                  'target': str(target), 'backup': str(backup),
                  'beforeSha256': sha(before), 'afterSha256': sha(after),
                  'beforeHeaderSha256': sha(header), 'afterHeaderSha256': sha(split_bytes(after)[0]),
                  'beforeBodySha256': sha(old_body), 'afterBodySha256': sha(generated_body),
                  'frontmatterPreserved': True, 'explicitReload': False,
                  'watchedEffect': 'chief Location may invalidate' if local else 'global agent Locations may invalidate'}
    else:
        text = before.decode('utf-8')
        if local and '; lean role' not in agent_parts(text)[1]:
            raise ValueError('fixed local target must be the managed canonical lean chief')
        after = repaired(text, str(brief)).encode('utf-8')
    if before == after:
        return result if body_only else 'same ' + str(target)
    if backup.exists():
        raise ValueError('archive collision; retain and reconcile before another deployment')
    if dry:
        return result if body_only else f'would archive {target} to {backup}; update only edit permissions'
    if target.read_bytes() != before:
        raise ValueError('concurrent target changed; not deployed')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open('xb') as f:
        f.write(before)
    if backup.read_bytes() != before or target.read_bytes() != before:
        raise ValueError('archive or concurrent target changed; not deployed')
    with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, delete=False) as f:
        f.write(after)
        temporary = Path(f.name)
    try:
        temporary.chmod(target.stat().st_mode & 0o777)
        DestinationRoot(home).validate_all([target])
        if target.read_bytes() != before:
            raise ValueError('concurrent target changed before replacement; not deployed')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    if target.read_bytes() != after:
        raise ValueError('deployment readback mismatch')
    return result if body_only else 'updated only chief edit permissions; archive: ' + str(backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('brief')
    parser.add_argument('home')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--revision', help='explicit immutable backup revision; default collision behavior is unchanged')
    parser.add_argument('--local', action='store_true', help='repair only the fixed installed canonical local chief metadata')
    parser.add_argument('--body-only', action='store_true', help='replace only the fixed managed chief body; preserve exact frontmatter')
    parser.add_argument('--expected-sha256', help='required exact current file hash for body-only mode, including no-op runs')
    args = parser.parse_args()
    result = deploy(args.brief, args.home, args.dry_run, args.revision, args.local, args.body_only, args.expected_sha256)
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)
