#!/usr/bin/env python3
"""Scoped local OpenCode installation. Never edit global settings or shared bins."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import re

from install_paths import DestinationRoot
from profiles import compose, load_profile, permissions, managed_surfaces
from render import SRC, expand, read
from courtesy import skill, MARKER as COURTESY_MARKER
from courtesy_owned import OwnedSkills
from service_resources import resource_outputs, resource_paths


def atomic(target, text):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(text)
    try:
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink()


def validate_directory(data):
    if not isinstance(data, dict) or set(data) != {'version', 'domains'} or type(data['version']) is not int or data['version'] != 1 or not isinstance(data['domains'], list):
        raise ValueError('invalid domain directory')
    ids, homes = set(), set()
    for row in data['domains']:
        if (not isinstance(row, dict) or set(row) != {'id','responsibility','server','home','pointer'}
                or row['server'] != 'local' or not isinstance(row['id'], str)
                or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', row['id'])
                or not isinstance(row['responsibility'], str) or not row['responsibility'].strip()
                or not isinstance(row['home'], str) or not Path(row['home']).is_absolute()
                or os.path.normpath(row['home']) != row['home']
                or row['pointer'] != str(Path(row['home']) / 'chief.json')
                or row['id'] in ids or row['home'] in homes):
            raise ValueError('malformed or ambiguous directory owner')
        ids.add(row['id']); homes.add(row['home'])
    return data


def main(selection, mode, hosts):
    if hosts and set(hosts) - {'opencode','home'}:
        raise ValueError('scoped profiles support local OpenCode/home only; no fake Claude/Codex policy')
    if hosts and 'opencode' not in hosts:
        raise ValueError('scoped home is inseparable from its local OpenCode adapter')
    profile = load_profile(selection)
    root = DestinationRoot(os.environ['HOME'])
    home = root.path / profile['home']
    shared = Path(os.environ.get('CHIEF_BRIEF_DIR', str(root.path / '.chief-of-staff'))).resolve()
    runway = Path(os.environ.get('CHIEF_RUNWAY_HOME', str(shared / 'runway'))).resolve()
    if home == shared or shared in home.parents or home in shared.parents:
        raise ValueError('domain home overlaps shared authority')
    directory = root.path / '.config/chief-of-staff/domains.json'
    inventory = home / '.kit-install.json'
    chief, lead, values = compose(profile, home, shared, runway, directory)
    marker = '<!-- managed by chief-of-staff scoped profile ' + profile['id'] + ' -->'
    managed = managed_surfaces(profile, home)
    outputs = {}
    for role, prompt in [('chief',chief),('lead',lead),('worker','You perform one bounded job for your lead. Use domain_identity for your id and domain_a2a_send for your lead\'s explicit local address with automatic reply. Use notes/ and output/ in this outcome only. Do not delegate, schedule, contact people or claim unverified completion. Return evidence and unresolved decisions to your lead.')]:
        header = {'description':profile['responsibility'] + ' (' + role + ')', 'mode':'primary',
                  'permissions':permissions(home, role, values['CHECKPOINT_NAME'], values['SHAPE_NAME'], shared, directory, managed)}
        # JSON is a valid YAML mapping; frontmatter fields are native V2 fields only.
        outputs[home / f'.opencode/agents/{profile[role+"_agent"]}.md'] = '---\n' + json.dumps(header,indent=2) + '\n---\n' + marker + '\n\n' + prompt + '\n'
    shape = expand(read('kits/chief/skills/shape/workflow.md'), {**values, 'TEMPLATE':read('kits/chief/skills/shape/PROJECT.template.md')})
    checkpoint = f'''# Domain checkpoint

Chief: sweep decisions, open questions, promises, receipts and outcome rows into
`{home}`. Read brief.md, open.md and principal.md as a fresh reader; archive closed
items. Confirm chief.json has your current domain_identity session and this home.
For `fresh`, use domain_a2a_create locally with agent `{profile['chief_agent']}`, directory
`{home}`, no goal mode; send the state-read handover via domain_a2a_send. Verify the new
chief.json before forwarding late arrivals; never overwrite the technical pointer.
Use `nest: false` for a fresh same-role session. Actual host transfer and goal-mode
activation still need the later bounded runtime proof; do not claim untested success.

Lead: use the independent lead checkpoint below, staying in this profile's scope.
For fresh lead handover ONLY use domain_lead_start with replacement: true,
the SAME outcome directory, explicit model, and the exact logged goal plus a
LEAD.md/state-read handover. Never substitute domain_a2a_create for lead goal mode.
The host bridge admits only the currently confirmed lead replacing itself.
If blocked/uncertain, keep the log and ask the owner to reconcile; never replay.
'''+expand(read('kits/lead/skills/checkpoint.md'), values)
    for name, workflow, agent in [(values['SHAPE_NAME'],shape,profile['chief_agent']), (values['CHECKPOINT_NAME'],checkpoint,None)]:
        header = 'description: Scoped ' + name + ('\nagent: '+agent if agent else '')
        outputs[home / f'.opencode/commands/{name}.md'] = '---\n'+header+'\n---\n'+marker+'\n\n'+workflow+'\n\nArguments: $ARGUMENTS\n'
        outputs[home / f'.opencode/skills/{name}/SKILL.md'] = f'---\nname: {name}\ndescription: Scoped {name}\n---\n{marker}\n\n{workflow}\n'
    outputs[home / '.opencode/skills/upstream-courtesy/SKILL.md'] = skill().replace(COURTESY_MARKER, marker)
    outputs.update(resource_outputs(home, marker))
    plugin = home / '.opencode/plugins/chief-domain/index.ts'
    outputs[plugin] = ''
    # Rollback validates installed ownership, never an optional external module.
    if mode != 'uninstall':
        setting = os.environ.get('CHIEF_A2A_MODULE')
        if not setting or not Path(setting).is_absolute():
            raise ValueError('set CHIEF_A2A_MODULE to an approved absolute opencode-a2a plugin path')
        transport = Path(setting).resolve(strict=True)
        native_root = os.environ.get('CHIEF_A2A_ROOT')
        if native_root and (not Path(native_root).is_absolute() or
                            (Path(native_root) / 'src/plugin.js').resolve(strict=True) != transport):
            raise ValueError('CHIEF_A2A_ROOT and CHIEF_A2A_MODULE must select the same transport')
        config = {**profile, 'home':str(home), 'directory':str(directory),
              'goal_binding':str(root.path / '.config/chief-of-staff/goal-bindings' / profile['id'] / 'binding.json'),
              'managed_paths':[str(p) for p in managed],
              'transport_module':transport.as_uri(), 'transport_sha256':hashlib.sha256(transport.read_bytes()).hexdigest()}
        outputs[plugin] = '// '+marker+'\nimport {makePlugin} from '+json.dumps((SRC / 'hosts/domain-policy/index.mjs').as_uri())+';\nexport default makePlugin('+json.dumps(config)+');\n'
    outputs[home / 'AGENTS.md'] = marker+f'\n\nRead brief.md, open.md and principal.md before answering or after compaction. Own only this domain. Use {values["CHECKPOINT_NAME"]} before handover. Shared models: {shared}/models.md (read-only). Use domain_identity, not shell, for your session id; maintain this home\'s chief.json.\n'
    if set(managed) != set(outputs):
        raise ValueError('managed instruction surface inventory mismatch')
    seeds = {home / 'brief.md':'# Running brief\n\n## Priorities\n\n## Projects\n\n## Stop conditions\n\n## Decisions\n\n## Parked\n',
             home / 'open.md':'# Open items\n', home / 'principal.md':'# Principal\n\n'+profile['tone']+'\n',
             home / 'chief.json':json.dumps(dict(session='', directory=str(home), updated=''))+'\n'}
    root.validate_all([inventory, directory, home / 'outcomes', *outputs, *seeds])
    if (home / 'outcomes').exists() and not (home / 'outcomes').is_dir():
        raise ValueError('outcomes path is not a directory')
    for target in seeds:
        if target.exists() and not target.is_file():
            raise ValueError('private seed is not a file')
    previous = json.loads(inventory.read_text()) if inventory.exists() else None
    if previous is not None and (not isinstance(previous, dict) or set(previous) != {'version','identity','owned','private_seeds'} or type(previous['version']) is not int or previous['version'] != 1):
        raise ValueError('invalid profile inventory')
    identity = {k:profile[k] for k in ('id','home','chief_agent','lead_agent','worker_agent')}
    relative = lambda p: str(p.relative_to(root.path))
    courtesy_path = relative(home / '.opencode/skills/upstream-courtesy/SKILL.md')
    expected_paths = {relative(p) for p in outputs}
    legacy_paths = expected_paths - {relative(p) for p in resource_paths(home)}
    if previous is not None and (previous['identity'] != identity or type(previous['owned']) is not dict
            or set(previous['owned']) not in (expected_paths, legacy_paths, legacy_paths - {courtesy_path})
            or any(type(h) is not str or not re.fullmatch('[0-9a-f]{64}', h) for h in previous['owned'].values())
            or previous['private_seeds'] != [relative(p) for p in seeds]):
        raise ValueError('installed scope changed; uninstall the original profile first')
    for target in outputs:
        if target.exists() and (not previous or relative(target) not in previous['owned'] or marker not in target.read_text()):
            raise ValueError('unowned scoped target: ' + str(target))
        if target.exists() and previous and hashlib.sha256(target.read_bytes()).hexdigest() != previous['owned'][relative(target)]:
            raise ValueError('modified managed file; reconcile before mutation: ' + str(target))
    courtesy_target = home / '.opencode/skills/upstream-courtesy/SKILL.md'
    courtesy_owned = OwnedSkills(root.path, {courtesy_target: outputs[courtesy_target]},
                                owner='scoped:' + profile['id']) if mode != 'print' else None
    if (previous and courtesy_target.exists() and
            hashlib.sha256(courtesy_target.read_bytes()).hexdigest() != previous['owned'].get(courtesy_path)):
        raise ValueError('modified courtesy inventory; reconcile before any mutation')
    registry = validate_directory(json.loads(directory.read_text())) if directory.exists() else {'version':1,'domains':[]}
    row = dict(id=profile['id'],responsibility=profile['responsibility'],server='local',home=str(home),pointer=str(home/'chief.json'))
    existing = next((r for r in registry['domains'] if r['id']==row['id']), None)
    if existing and existing != row:
        raise ValueError('directory owner conflict')
    if not existing and any(r['home']==row['home'] for r in registry['domains']):
        raise ValueError('directory home conflict')
    technical = next((r for r in registry['domains'] if r['id']=='technical'), None)
    if technical and technical['home'] != str(shared):
        raise ValueError('shared technical owner differs from configured authority')
    if mode in ('print','dry'):
        for target, text in outputs.items():
            print('=== '+str(target)+'\n'+text if mode=='print' else 'would manage '+str(target))
        return
    if mode == 'uninstall':
        if not previous:
            raise ValueError('no owned profile inventory')
        courtesy_owned.uninstall()
        for target in outputs:
            if target == courtesy_target: continue
            if target.exists(): target.unlink()
        inventory.unlink()
        registry['domains'] = [r for r in registry['domains'] if r['id'] != row['id']]
        atomic(directory,json.dumps(registry,indent=2)+'\n')
        print('removed scoped managed files; private seeds retained')
        return
    if mode != 'install': raise ValueError('invalid mode')
    if not existing: registry['domains'].append(row)
    if not any(r['id']=='technical' for r in registry['domains']):
        registry['domains'].append(dict(id='technical',responsibility='Technical projects and technical ideas',server='local',home=str(shared),pointer=str(shared/'chief.json')))
    validate_directory(registry)
    courtesy_owned.install()
    for target, text in outputs.items():
        if target != courtesy_target: atomic(target,text)
    for target, text in seeds.items():
        if not target.exists(): atomic(target,text)
    (home / 'outcomes').mkdir(exist_ok=True)
    atomic(directory,json.dumps(registry,indent=2)+'\n')
    manifest = dict(version=1, identity=identity, owned={relative(p):hashlib.sha256(t.encode()).hexdigest() for p,t in outputs.items()}, private_seeds=[relative(p) for p in seeds])
    atomic(inventory,json.dumps(manifest,indent=2)+'\n')
    print('installed '+profile['id']+' in '+str(home)+' (local OpenCode; runtime proof pending)')


if __name__ == '__main__':
    try: main(sys.argv[1],sys.argv[2],sys.argv[3:])
    except (ValueError, KeyError, OSError, TypeError) as e: sys.exit('install.sh: '+str(e))
