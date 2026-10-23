"""Optional source checkout validation; native session locations remain independent."""
import os
import subprocess
from pathlib import Path


def git(directory, *args):
    try:
        return subprocess.run(['git', '-C', directory, *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=5).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('checkout requires an existing registered same-repository worktree') from exc


def checkout_identity(task):
    if 'checkout' not in task:
        return None  # Legacy non-repository directories remain supported.
    value = task['checkout']
    if not isinstance(value, str) or not value.strip():
        raise ValueError('checkout must be an existing worktree path')
    try:
        checkout = str(Path(value).expanduser().resolve(strict=True))
        if not Path(checkout).is_dir():
            raise ValueError('checkout must be a directory')
        common = git(task['directory'], 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()
        other = git(checkout, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()
        top = git(checkout, 'rev-parse', '--show-toplevel').decode().strip()
        roots = [os.fsdecode(part[len(b'worktree '):]) for part in
                 git(task['directory'], 'worktree', 'list', '--porcelain', '-z').split(b'\0')
                 if part.startswith(b'worktree ')]
        if Path(common).resolve() != Path(other).resolve() or checkout not in roots or top != checkout:
            raise ValueError('checkout must be a registered same-repository worktree root')
        git_dir = Path(git(checkout, 'rev-parse', '--absolute-git-dir').decode().strip()).resolve(strict=True)
        stat = git_dir.stat()
    except OSError as exc:
        raise ValueError('checkout must be an existing registered worktree') from exc
    task['checkout'] = checkout
    return {'common_dir': str(Path(common).resolve()), 'git_dir': str(git_dir),
            'device': stat.st_dev, 'inode': stat.st_ino}


def revalidate_checkout(attempt):
    task = dict(attempt['task'])
    identity = checkout_identity(task)
    if identity != attempt.get('checkout_identity') or task.get('checkout') != attempt['task'].get('checkout'):
        raise ValueError('reserved checkout identity changed; reconcile before continuing')


def source_directory(task):
    return task.get('checkout', task['directory'])
