"""Retire exact known-owned executable files, preserving historical data."""
import fnmatch
import hashlib
from pathlib import Path

RETIRED = ('docket-own-milestone.js', 'own-plan-checkbox.js', 'memory-access-proof.js',
           'heartbeat-proof-*.md', '*-edit-proof-kit-*.md', '*-reset-staged-*.md',
           'lead.md', 'chief-of-staff.md')


def retire(root, known_owned, dry=False):
    root = Path(root).resolve()
    moves = []
    for relative, digest in known_owned.items():
        path = root / relative
        if (Path(relative).is_absolute() or '..' in Path(relative).parts
                or not any(fnmatch.fnmatchcase(path.name, p) for p in RETIRED)):
            raise ValueError('not a named retired executable')
        if path.parent not in (root / '.opencode/plugins', root / '.opencode/agents'):
            raise ValueError('retirement outside executable directories')
        if not path.exists():
            continue
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('symlink retired file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('retired file changed; preserve/reconcile: ' + str(path))
        target = root / '.opencode/retired-role-artifacts' / relative
        if target.exists():
            raise ValueError('retirement archive collision')
        moves.append((path, target))
    if dry:
        return [str(p) for p, _ in moves]
    for path, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True); path.rename(target)
    return [str(p) for p, _ in moves]


def remove_shims(home, known_owned, dry=False):
    """Delete only receipt-pinned obsolete executable shims, not their evidence."""
    home = Path(home).resolve(); paths = {}
    names = {'docket-own-milestone.js', 'own-plan-checkbox.js', 'memory-access-proof.js'}
    proof_roles = ('heartbeat-proof-*.md', '*-edit-proof-kit-*.md')
    for name, digests in known_owned.items():
        original = Path(name)
        if not original.is_absolute() or not original.is_relative_to(home):
            continue
        plugin = original.parent.name == 'plugins' and original.parent.parent.name == '.opencode' and original.name in names
        role = original.parent.name == 'agents' and original.parent.parent.name == '.opencode' and any(fnmatch.fnmatchcase(original.name, p) for p in proof_roles)
        runtime = original == home / '.local/share/chief-of-staff/plans/checkbox.mjs'
        if not (plugin or role or runtime): continue
        targets = [original]
        if plugin or role:
            root = original.parent.parent.parent
            targets.append(root / '.opencode/retired-role-artifacts' / original.relative_to(root))
        for target in targets:
            if not target.exists() and not target.is_symlink(): continue
            if target.is_symlink() or any(p.is_symlink() for p in target.parents):
                raise ValueError('symlink retired shim; preserve: ' + str(target))
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest not in digests:
                raise ValueError('obsolete shim changed; preserve/reconcile: ' + str(target))
            paths[target] = digest
    if not dry:
        for target, digest in paths.items():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('shim changed after preflight; preserve: ' + str(target))
            target.unlink()
    return {str(p): digest for p, digest in paths.items()}
