#!/usr/bin/env python3
"""Maintain one receipt-owned ordinary-call entry; never execute the owner CLI.

Only an already installed binding is supported. No roles, permissions, runtime,
service, attempt, enrollment or status writes; the native entry reports registration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from install_paths import DestinationRoot

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'ordinary-chief-call-maintenance'
KEYS = {'nodePath', 'codeRoot', 'chiefPointerFile', 'directory', 'agentID', 'attemptDirectory', 'cliSha256'}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def render(binding, module, version, status):
    text = (ROOT / 'services/voicestack/ordinary-call-entry.js').read_text()
    for token, value in {'__VERSION_MODULE__': str(version), '__CALL_MODULE__': str(module),
                         '__BINDING__': binding, '__STATUS_FILE__': str(status)}.items():
        if text.count(token) != 1: raise ValueError('ordinary entry template changed')
        text = text.replace(token, json.dumps(value))
    return text


def install(location, revision, dry=False):
    home = Path.home().resolve(); chief = Path(location)
    if not chief.is_absolute() or chief.resolve() != chief or not chief.is_dir():
        raise ValueError('existing canonical chief Location required')
    if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', revision):
        raise ValueError('safe revision basename required; no separators or traversal')
    original = chief / 'archive/reset-20261022-heartbeat/install-ordinary-call-20261022.json'
    module = home / '.local/share/chief-of-staff/voicestack/ordinary-call.mjs'
    version = home / '.local/share/chief-of-staff/heartbeat/version.mjs'
    wrapper = chief / '.opencode/plugins/chief-ordinary-call.js'
    status = chief / '.opencode/reset-install/ordinary-call-runtime.json'
    archive = chief / 'archive/reset-ordinary-call-maintenance' / revision
    backup = archive / 'chief-ordinary-call.js.txt'; receipt = archive / 'install.json'
    DestinationRoot(home).validate_all([original, module, version, wrapper, status, backup, receipt])
    original_bytes = original.read_bytes(); owner = json.loads(original_bytes)
    binding = owner.get('binding')
    if owner.get('scope') != 'ordinary-chief-call-only' or not isinstance(binding, dict) or set(binding) != KEYS:
        raise ValueError('existing exact ordinary-call owner receipt required')
    if (binding['directory'] != str(chief) or binding['chiefPointerFile'] != str(chief / 'chief.json')
            or binding['agentID'] != 'chief-of-staff' or binding['attemptDirectory'] != str(chief / 'ordinary-call-attempts')
            or any(not isinstance(binding[k], str) or not Path(binding[k]).is_absolute() for k in ('nodePath', 'codeRoot'))
            or not isinstance(binding['cliSha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', binding['cliSha256'])):
        raise ValueError('existing binding differs from the fixed chief capability')
    # Reuse the reviewed2.0.32 floor/helper already used by the source installer;
    # neither that helper nor the refusal/call runtime is changed by maintenance.
    module_bytes = module.read_bytes(); version_bytes = version.read_bytes()
    if sha(module_bytes) != owner.get('after', {}).get(str(module)) or module_bytes != (ROOT / 'services/voicestack/ordinary-call.mjs').read_bytes():
        raise ValueError('ordinary-call runtime drift; review without replacing it')
    if version_bytes != (ROOT / 'heartbeat/version.mjs').read_bytes():
        raise ValueError('reviewed installed minimum-version helper required')
    cli = Path(binding['codeRoot']) / 'bridge/reachout.mjs'
    cli_bytes = cli.read_bytes()
    if sha(cli_bytes) != binding['cliSha256']:
        raise ValueError('reviewed CLI changed; do not execute or rebind it')
    guard_paths = [chief / 'chief.json', chief / 'heartbeat/pilot-options.json',
                   chief / '.opencode/agents/chief-of-staff.md', chief / '.opencode/opencode.json']
    DestinationRoot(home).validate_all(guard_paths + [Path(binding['attemptDirectory'])])
    guards = {p: p.read_bytes() if p.exists() else None for p in guard_paths}
    pointer = json.loads(guards[chief / 'chief.json'])
    if pointer.get('directory') != str(chief) or not re.fullmatch(r'ses_[A-Za-z0-9]+', pointer.get('session', '')):
        raise ValueError('current existing chief pointer required')
    attempt_dir = Path(binding['attemptDirectory']); attempt_stat = attempt_dir.stat()
    if not stat.S_ISDIR(attempt_stat.st_mode) or attempt_stat.st_uid != os.getuid() or attempt_stat.st_mode & 0o077:
        raise ValueError('existing private attempt directory required; never repair it')
    before = wrapper.read_bytes(); wanted = render(binding, module, version, status).encode()
    known = {owner.get('after', {}).get(str(wrapper))}
    for old_receipt in archive.parent.glob('*/install.json'):
        value = json.loads(old_receipt.read_text())
        if value.get('scope') == SCOPE and value.get('binding') == binding and value.get('originalReceiptSha256') == sha(original_bytes):
            known.add(value.get('after', {}).get(str(wrapper)))
    if sha(before) not in known:
        raise ValueError('installed wrapper is not exact receipt-owned bytes; preserve')
    result = {'status': 'same' if before == wanted else 'would-update' if dry else 'updated',
              'location': str(chief), 'target': str(wrapper), 'binding': binding,
              'beforeSha256': sha(before), 'afterSha256': sha(wanted), 'backup': str(backup), 'receipt': str(receipt),
              'changedTargets': [] if before == wanted else [str(wrapper)],
              'minimumNativeVersion': '2.0.32', 'activation': 'watched entry replacement only; no explicit reload/restart',
              'ownerCLIExecuted': False}
    if before == wanted: return result
    if archive.exists(): raise ValueError('immutable revision archive collision; no overwrite')
    if dry: return result
    # Recheck every dependency/guard immediately before the sole executable update.
    observed = {original: original_bytes, module: module_bytes, version: version_bytes,
                cli: cli_bytes, wrapper: before, **guards}
    if any((p.read_bytes() if p.exists() else None) != value for p, value in observed.items()):
        raise ValueError('expected installed bytes changed; no write')
    archive.mkdir(parents=True, exist_ok=False, mode=0o700)
    with backup.open('xb') as out: out.write(before)
    saved = {'scope': SCOPE, 'binding': binding, 'originalReceiptSha256': sha(original_bytes),
             'beforeSha256': sha(before), 'after': {str(wrapper): sha(wanted)},
             'preserved': {str(p): sha(v) if v is not None else None for p, v in observed.items() if p != wrapper}}
    with receipt.open('x') as out: json.dump(saved, out, indent=2); out.write('\n')
    if backup.read_bytes() != before or any((p.read_bytes() if p.exists() else None) != value for p, value in observed.items()):
        raise ValueError('expected bytes changed after backup; executable not replaced')
    fd, temporary = tempfile.mkstemp(dir=wrapper.parent, prefix='.ordinary-call-')
    try:
        os.fchmod(fd, stat.S_IMODE(wrapper.stat().st_mode))
        with os.fdopen(fd, 'wb') as out:
            out.write(wanted); out.flush(); os.fsync(out.fileno())
        if wrapper.read_bytes() != before: raise ValueError('wrapper changed before atomic replace')
        os.replace(temporary, wrapper)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    if wrapper.read_bytes() != wanted or any((p.read_bytes() if p.exists() else None) != v for p, v in guards.items()):
        raise ValueError('installed/guard readback changed; inspect, never restore blindly')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('location', type=Path); parser.add_argument('--revision', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.location, args.revision, args.dry_run), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error))
