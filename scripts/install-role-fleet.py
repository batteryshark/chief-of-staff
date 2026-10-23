#!/usr/bin/env python3
"""Normal lead prompt/shared milestone migration during an owner-coordinated idle window.

Read native identity and Knowledge; write only managed roles/runtime and permission config.
Never enroll, release, prompt, re-goal or change a session/model. No service restart.
Roster discovery here migrates existing installations only; generic own-file access
for future lead Locations is supplied by the global role, not this enumeration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from access_policy import agent_parts
from install_paths import DestinationRoot
from role_contract import MARK, agent, canonical, knowledge_plans, project_config
from role_cleanup import retire
from lean_roles import procedures

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()


def known_installed(home):
    owned = {}
    for receipt in (home / '.chief-of-staff/archive').glob('reset-*/install-*.json'):
        value = json.loads(receipt.read_text())
        for target, digest in value.get('after', {}).items():
            if isinstance(digest, str) and len(digest) == 64:
                owned.setdefault(target, set()).add(digest)
    return owned


def retained_local_rules(text, location, plans, brief):
    """Retire known-generated broad memory rules, retain independent asks/denials."""
    allowed = {'LEAD.md', 'PROJECT.md', '*/LEAD.md', 'lead/*', '*/lead/*',
               location + '/LEAD.md', location + '/PROJECT.md', location + '/lead/*',
               brief + '/inbox/*.md', *plans}
    result = []
    for rule in agent_parts(text)[2]:
        if rule['action'] == 'edit':
            if rule['resource'] == '*' and rule['effect'] == 'deny':
                continue
            if rule['effect'] == 'allow':
                if rule['resource'] not in allowed:
                    raise ValueError('unrecognized local edit grant; preserve/reconcile: ' + rule['resource'])
                continue
        result.append(rule)
    return result


def migrate(docket_source, included=(), dry=False):
    home = Path.home(); brief = home / '.chief-of-staff'
    source = Path(canonical(str(docket_source)))
    sys.path.insert(0, str(source))
    from docket.host import configured_adapter
    adapter = configured_adapter()
    roster = home / '.docket/lead-checkins.jsonl'; raw = roster.read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    bindings = []; snapshots = {}
    for row in rows:
        if row.get('state') not in ('active', 'hold'):
            continue
        code, response = adapter._request('GET', '/api/session/' + row['session'])
        native = response.get('data', response)
        if (code != 200 or native.get('id') != row['session'] or native.get('agent') != 'lead'
                or native.get('time', {}).get('archived')
                or native.get('location', {}).get('directory') != row['directory']):
            raise ValueError('enrolled native identity changed; no session repair')
        canonical(row['directory'])
        snapshots[row['session']] = native
        bindings.append(dict(sessionID=row['session'], agentID='lead', directory=row['directory']))
    locations = list(dict.fromkeys([b['directory'] for b in bindings] + [canonical(str(p)) for p in included]))
    owned = known_installed(home); configs = {}; retirements = {}
    for location in locations:
        directory = Path(location); path = directory / '.opencode/opencode.json'
        if path.with_suffix('.jsonc').exists() or (directory / 'opencode.jsonc').exists():
            raise ValueError('JSONC source must be reconciled without shadowing: ' + location)
        plans = knowledge_plans(location, str(home))
        existing = json.loads(path.read_text()) if path.exists() else {}
        local = directory / '.opencode/agents/lead.md'
        if local.exists():
            if sha(local.read_bytes()) not in owned.get(str(local), set()):
                raise ValueError('local lead changed since known installation: ' + location)
            current = existing.setdefault('agents', {}).setdefault('lead', {})
            current.setdefault('permissions', []).extend(retained_local_rules(local.read_text(), location, plans, str(brief)))
            retirements.setdefault(location, {})[str(local.relative_to(directory))] = sha(local.read_bytes())
        configs[path] = json.dumps(project_config(existing, 'lead', str(home), str(brief), location, plans), indent=2) + '\n'
        for name in ('docket-own-milestone.js', 'own-plan-checkbox.js', 'memory-access-proof.js'):
            old = directory / '.opencode/plugins' / name
            if old.exists():
                if sha(old.read_bytes()) not in owned.get(str(old), set()):
                    raise ValueError('old wrapper changed since known installation: ' + str(old))
                retirements.setdefault(location, {})[str(old.relative_to(directory))] = sha(old.read_bytes())
    runtime = home / '.local/share/chief-of-staff/docket'
    helpers = ('docket/milestone.py', 'docket/checkins.py', 'docket/parse.py', 'docket/__init__.py')
    binding = dict(pythonPath='/usr/bin/python3', sourceRoot=str(source), home=str(home), callers=bindings,
                   sourceHashes={p: sha((source / p).read_bytes()) for p in helpers})
    runtime_files = {runtime / name: (ROOT / 'services/docket' / name).read_text() for name in ('milestone.mjs', 'shared.js')}
    runtime_files[runtime / 'binding.json'] = json.dumps(binding, indent=2) + '\n'
    # Install the reusable hold/archive boundary without changing Docket's service ABI.
    runtime_files[home / '.local/share/chief-of-staff/heartbeat/records.mjs'] = (ROOT / 'heartbeat/records.mjs').read_text()
    skills = {home / '.config/opencode/skills' / ident / 'SKILL.md': text for ident, text in procedures(str(brief)).items()}
    for target in skills:
        if target.exists() and MARK not in target.read_text():
            raise ValueError('unmanaged global procedure; preserve: ' + str(target))
    global_role = home / '.config/opencode/agents/lead.md'
    if global_role.exists() and MARK not in global_role.read_text():
        raise ValueError('unmanaged global lead; preserve')
    registration = home / '.config/opencode/plugins/chief-own-milestone.js'
    wrapper = '// managed by chief-of-staff/install.sh; single shared milestone registration\nexport {default} from ' + json.dumps((runtime / 'shared.js').as_uri()) + ';\n'
    if registration.exists() and registration.read_text() != wrapper:
        raise ValueError('shared registration changed; preserve')
    files = {**configs, **runtime_files, **skills, global_role: agent('lead', str(home), str(brief)), registration: wrapper}
    DestinationRoot(home).validate_all(files)
    for location, known in retirements.items():
        retire(location, known, dry=True)
    if roster.read_bytes() != raw:
        raise ValueError('roster changed during discovery; retry at coordinated checkpoint')
    if dry:
        return {'status': 'would-update', 'locations': locations, 'files': [str(p) for p in files], 'retirements': retirements}
    for target, text in configs.items():
        if target.exists() and target.read_text() == text:
            continue
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
    for target, text in runtime_files.items():
        if target.exists() and target.read_text() == text:
            continue
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
    for target, text in skills.items():
        if target.exists() and target.read_text() == text:
            continue
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
    # Old native-version-pinned wrappers leave the executable directories before the shared entry.
    for location, known in retirements.items():
        retire(location, {p: h for p, h in known.items() if p.endswith('.js')})
    for target in (global_role, registration):
        if target.exists() and target.read_text() == files[target]:
            continue
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(files[target])
    for location, known in retirements.items():
        retire(location, {p: h for p, h in known.items() if p.endswith('.md')})
    if roster.read_bytes() != raw:
        raise ValueError('roster changed; no roster writes made, inspect owner activity')
    for sid, before in snapshots.items():
        code, response = adapter._request('GET', '/api/session/' + sid); after = response.get('data', response)
        keys = ('id', 'agent', 'model', 'location', 'permissions')
        if code != 200 or any(before.get(k) != after.get(k) for k in keys) or before.get('metadata', {}).get('openchamber', {}).get('goal') != after.get('metadata', {}).get('openchamber', {}).get('goal'):
            raise ValueError('native identity/model/goal changed during migration; inspect, never restore blindly')
    return {'status': 'updated', 'locations': locations, 'callers': bindings, 'rosterBytesPreserved': True, 'nativeIdentityModelGoalsPreserved': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docket-source', required=True, type=Path)
    parser.add_argument('--include-location', action='append', type=Path, default=[])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(migrate(args.docket_source, args.include_location, args.dry_run), indent=2))
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
