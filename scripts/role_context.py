"""Pure install-time role diet compiler. No discovery, config writes or permission grants.

The caller supplies a fully loaded registry and reviewed exact per-role allowlist.
Missing allowed IDs fail closed: an early startup snapshot cannot silently compile.
This validates inventory coverage, not that the host finished discovery; the caller
must establish that at the native request boundary. Native/harness catalogs must
both be included. No inferred Galley names or wildcard tool aliases are accepted.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from access_policy import agent_parts

ROLES = frozenset(('chief', 'lead', 'writer', 'dispatcher'))


def exposure_policy():
    return json.loads((Path(__file__).resolve().parents[1] / 'services/role-policy.json').read_text())


def exposure_denials(role):
    """Preassembly catalog gates, distinct from resource access permissions."""
    return [{'action': action, 'resource': '*', 'effect': 'deny'}
            for action in exposure_policy().get(role, {}).get('denyActions', [])]


# Official V2 /permissions actions; worktree_remove's declared edit action is
# confirmed by the clean installed-2.1.3 finding. Do not infer other opencode IDs.
NATIVE_ACTIONS = {name: name for name in (
    'read', 'glob', 'grep', 'shell', 'skill', 'subagent', 'question', 'webfetch',
    'websearch', 'execute', 'opencode_list_mcp_resources', 'opencode_read_mcp_resource')}
NATIVE_ACTIONS.update(dict(patch='edit', write='edit', edit='edit',
                           opencode_worktree_remove='edit'))


def _actions(tool_actions):
    if tool_actions is None:
        return dict(NATIVE_ACTIONS)
    if not isinstance(tool_actions, dict):
        raise ValueError('tool_actions must be verified tool-ID/action metadata')
    result = dict(NATIVE_ACTIONS)
    for tool, action in tool_actions.items():
        _ids([tool], 'tool_actions tool')
        if action is not None:
            _ids([action], 'tool_actions action')
        if tool in NATIVE_ACTIONS and action != NATIVE_ACTIONS[tool]:
            raise ValueError('declared native permission action mismatch: ' + tool)
        if (tool.startswith('opencode_') and tool not in NATIVE_ACTIONS
                and action is not None and action not in NATIVE_ACTIONS.values()):
            raise ValueError('unsupported native permission mapping: ' + tool)
        result[tool] = action
    return result


def _ids(value, label):
    if not isinstance(value, list):
        raise ValueError(label + ' must be a list')
    if any(not isinstance(item, str) or not item or item.strip() != item
           or any(c.isspace() or c in '*?[]{}' for c in item) for item in value):
        raise ValueError(label + ' must contain exact nonempty IDs')
    if len(value) != len(set(value)):
        raise ValueError(label + ' contains duplicate IDs')
    return value


def _inventory(value, label):
    if not isinstance(value, dict) or set(value) != {'tools', 'skills'}:
        raise ValueError(label + ' requires exactly tools and skills')
    return {kind: _ids(value[kind], label + '.' + kind) for kind in ('tools', 'skills')}


def compile_denials(role, registry, allowlist, *, tool_actions=None):
    """Return {role: [exact deny entries]} without changing any supplied object.

    Allowlist is the reviewed exact role inventory, not patterns. Requiring every
    listed ID in registry prevents the known early-discovery failure from silently
    dropping a needed dependency. Writer inventory must be reviewed by Galley owner.
    """
    if not isinstance(role, str) or role not in ROLES:
        raise ValueError('unsupported role')
    registry = _inventory(registry, 'registry')
    allowed = _inventory(allowlist, 'allowlist')
    if not registry['tools'] or not allowed['tools']:
        raise ValueError('incomplete role tool registry/allowlist')
    if role == 'dispatcher':
        if allowed != {'tools': ['heartbeat_resolve'], 'skills': []}:
            raise ValueError('dispatcher must remain resolve-only')
    else:
        if not allowed['skills']:
            raise ValueError('incomplete role skill inventory')
        if role == 'chief' and any(
            skill not in ('checkpoint', 'upstream-courtesy', 'shape', 'deep-research')
            and not skill.startswith('reset-') for skill in allowed['skills']
        ):
            raise ValueError('unsupported chief skill')
    for kind in ('tools', 'skills'):
        missing = set(allowed[kind]) - set(registry[kind])
        if missing:
            raise ValueError('incomplete registry: missing ' + kind + ' ' + ', '.join(sorted(missing)))
    actions = _actions(tool_actions)
    allowed_actions = {actions[tool] for tool in allowed['tools'] if tool in actions}
    denies = []
    for tool in registry['tools']:
        if tool in allowed['tools']:
            continue
        if tool not in actions:
            raise ValueError('excluded tool requires verified permission metadata: ' + tool)
        action = actions[tool]
        if action is None:  # Explicitly reviewed direct-schema-only coverage.
            continue
        # Shared actions are resource policies, not independent tool switches.
        # Never erase own-file grants to hide worktree_remove/patch/write/edit.
        if action == 'edit' or action in allowed_actions:
            continue
        rule = {'action': action, 'resource': '*', 'effect': 'deny'}
        if rule not in denies:
            denies.append(rule)
    denies += [{'action': 'skill', 'resource': skill, 'effect': 'deny'}
               for skill in registry['skills'] if skill not in allowed['skills']]
    return {role: denies}


def append_denials(existing, role, registry, allowlist, *, tool_actions=None):
    """Keep all existing rules/order (including duplicates), append only new denies."""
    if not isinstance(existing, list):
        raise ValueError('existing rules must be a list')
    for rule in existing:
        if (not isinstance(rule, dict) or set(rule) != {'action', 'resource', 'effect'}
                or not all(isinstance(rule[k], str) and rule[k] for k in rule)
                or rule['effect'] not in ('allow', 'ask', 'deny')):
            raise ValueError('unsupported existing permission rule')
        if rule['action'] in NATIVE_ACTIONS and NATIVE_ACTIONS[rule['action']] != rule['action']:
            raise ValueError('existing tool-ID permission requires owner reconciliation')
    result = deepcopy(existing)
    for rule in compile_denials(role, registry, allowlist, tool_actions=tool_actions)[role]:
        if rule not in result:
            result.append(rule)
    return result


def amend_header(text, role, registry, allowlist, *, tool_actions=None):
    """Preserve body and every non-permissions header byte; refuse JSON headers.

    Native YAML block/inline-JSON permissions are parsed by the existing narrow
    kit decoder. JSON frontmatter is deliberately refused rather than rewriting
    unrelated metadata. A missing permission field is safely appended.
    """
    header, body, existing, fields, match = agent_parts(text)
    if fields is not None:
        raise ValueError('JSON frontmatter requires byte-preserving native wiring')
    updated = append_denials(existing, role, registry, allowlist, tool_actions=tool_actions)
    if updated == existing:
        return text
    replacement = 'permissions: ' + json.dumps(updated) + '\n'
    if match:
        # agent_parts matched against header + newline; preserve that convention.
        original = header + '\n'
        header = (original[:match.start()] + replacement + original[match.end():]).removesuffix('\n')
    else:
        header += '\n' + replacement.rstrip('\n')
    return '---\n' + header + '\n---\n' + body


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(path, role, registry, allowlist, expected_sha256, *, tool_actions=None):
    """Dry-run one existing managed agent; returns serializable exact-hash manifest."""
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError('canonical existing nonsymlink agent required')
    raw = path.read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError('agent changed before prepare')
    text = raw.decode()
    if 'managed by chief-of-staff/install.sh' not in text:
        raise ValueError('unmanaged agent; owner reconciliation required')
    after = amend_header(text, role, registry, allowlist, tool_actions=tool_actions).encode()
    return {'path': str(path), 'role': role, 'beforeSha256': sha(raw),
            'afterSha256': sha(after), 'afterText': after.decode()}


def _atomic(path, raw):
    mode = path.stat().st_mode & 0o777
    fd, temp = tempfile.mkstemp(prefix=path.name + '.context-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(manifest, backup):
    """Exact-byte guarded single-file apply; backup must be a new private file."""
    path = Path(manifest['path']); backup = Path(backup)
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError('agent path changed')
    raw = path.read_bytes(); after = manifest['afterText'].encode()
    if sha(raw) != manifest['beforeSha256'] or sha(after) != manifest['afterSha256']:
        raise ValueError('manifest/preimage changed')
    with backup.open('xb') as stream:
        os.chmod(backup, 0o600)
        stream.write(raw)
    # Recheck after backup creation before the atomic replacement.
    if path.read_bytes() != raw:
        raise ValueError('agent changed during backup')
    _atomic(path, after)
    return {'path': str(path), 'backup': str(backup), 'beforeSha256': sha(raw), 'afterSha256': sha(after)}


def rollback(receipt):
    """Restore only our exact postimage, never overwrite subsequent owner work."""
    path = Path(receipt['path']); raw = Path(receipt['backup']).read_bytes()
    if path.is_symlink() or path.resolve() != path or sha(raw) != receipt['beforeSha256']:
        raise ValueError('rollback path/backup changed')
    if sha(path.read_bytes()) != receipt['afterSha256']:
        raise ValueError('postimage changed; preserve owner work')
    _atomic(path, raw)
