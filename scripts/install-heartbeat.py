#!/usr/bin/env python3
"""Install the explicit two-Location pilot, disabled-first; archive owned replacements."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import tempfile
from access_policy import agent_parts

from install_paths import DestinationRoot
from lean_roles import budget, catalog, installed_startup, procedures, render_role
from render import render

ROOT = Path(__file__).resolve().parents[1]
MARK = 'managed by chief-of-staff/install.sh'


def section(file, heading):
    lines = Path(file).read_text().splitlines()
    start = lines.index(heading) + 1
    level = len(heading.split(' ')[0])
    end = next((i for i in range(start, len(lines)) if re.match(r'^#{1,' + str(level) + r'} ', lines[i])), len(lines))
    return '\n'.join(lines[start:end]).strip()


def plan(config, phase):
    if phase == 'roles':
        raise ValueError('retired local-role migration; use install.sh role contract')
    chief, origin = Path(config['chiefLocation']), Path(config['originDirectory'])
    for path in (chief, origin):
        if not path.is_absolute() or path.resolve() != path or not path.is_dir():
            raise ValueError('existing canonical pilot Locations required')
    runtime = Path.home() / '.local/share/chief-of-staff/heartbeat'
    options_path = chief / 'heartbeat/pilot-options.json'
    previous = json.loads(options_path.read_text()) if options_path.exists() else {}
    memory = chief / 'heartbeat/bus'
    goal_binding = config['goalBinding']
    if 'objectiveFilePath' in goal_binding:
        effective = Path(goal_binding['objectiveFilePath']).read_text().strip()
        if hashlib.sha256(effective.encode()).hexdigest() != goal_binding['effectiveObjectiveSha256']:
            raise ValueError('reviewed resolved goal objective changed; preserve and reconcile')
    files = {runtime / p.name: p.read_text() for p in (ROOT / 'heartbeat').iterdir() if p.suffix in ('.mjs', '.py', '.js', '.json', '.md') and not p.name.endswith('.test.mjs')}
    files[Path.home() / '.local/bin/chief-nod'] = render('scripts/chief-nod', str(chief))
    log = origin / 'LEAD.md'
    # Quotes come from EXISTING exact reviewed sections, never a manufactured all-clear.
    holds = {'global': [{'file': str(log), 'heading': '## Stop conditions', 'allowedQuote': section(log, '## Stop conditions')}],
             'lanes': {'reset': [{'file': str(log), 'heading': '## Goal', 'allowedQuote': section(log, '## Goal')}]}}
    recipients = config.get('postOnlyRecipients', [])
    if any(set(r) != {'session', 'directory', 'standingSections'} or not r['session'].startswith('ses_')
           or not Path(r['directory']).is_absolute() or not Path(r['directory']).is_dir()
           or Path(r['directory']).resolve() != Path(r['directory']) for r in recipients):
        raise ValueError('explicit canonical post-only recipients required')
    origin_directories = {config['originSession']: str(origin), **{r['session']:r['directory'] for r in recipients}}
    if len(origin_directories) != 1 + len(recipients): raise ValueError('duplicate origin binding')
    sending = config.get('nodSendEnabled', False)
    cutoff = previous.get('nodNotBefore') if previous.get('nodSendEnabled') else int(time.time() * 1000)
    options = {'enabled': phase != 'prepare', 'memoryRoot': str(memory), 'chiefPointerFile': str(chief / 'chief.json'),
               'agent': 'heartbeat-pilot-dispatcher', 'model': {'providerID': 'openai', 'id': 'gpt-6-luna', 'variant': 'medium'},
               'chiefInstructionsFile': str(Path.home() / '.config/opencode/agents/chief-of-staff.md'),
               'standingSections': [s for r in recipients for s in r['standingSections']] + config['standingSections'],
               'originSessions': list(origin_directories), 'originDirectories': origin_directories, 'originDirectory': str(origin),
               'goalSessions': [config['originSession']], 'holdBindings': {str(origin): holds},
               'goalBindings': {config['originSession']: config['goalBinding']}, 'docketSource': config['docketSource'],
               'minimumNativeVersion': config['nativeVersion'], 'rosterFile': str(Path.home() / '.docket/lead-checkins.jsonl'),
               'nodReadEnabled': True, 'nodSendEnabled': sending,
               **({'nodNotBefore': cutoff} if sending else {}), 'deferInitialTick': True, 'revision': config.get('revision', ''),
               'nodCommand': [str(Path.home() / '.local/bin/chief-nod'), '--answer-route', 'heartbeat-bus'],
               'nodFeedFile': str(runtime / 'nod-feed.mjs')}
    if options_path.exists():
        # Reinstall cannot silently bless a changed hold/goal into a fresh allowed state.
        old_goals = previous['goalBindings']
        new_goals = options['goalBindings']
        # Accepted file-mode correction may enrich the former raw-metadata binding,
        # but can never change any previously reviewed identity/scope value.
        same_goals = (set(old_goals) == set(new_goals) and all(
            all(new_goals[sid].get(k) == value for k, value in old.items())
            and set(new_goals[sid]) - set(old) <= {'objectiveFilePath', 'effectiveObjectiveSha256'}
            for sid, old in old_goals.items()))
        if previous['holdBindings'] != options['holdBindings'] or not same_goals:
            raise ValueError('reviewed goal/hold changed; reconcile explicitly, never refresh the allowed quote')
    files[options_path] = json.dumps(options, indent=2) + '\n'
    tools = dict(re.findall(r"^  (\w+): '([^']+)'", (ROOT / 'heartbeat/plugin.mjs').read_text(), re.M))
    locations = [('chief', chief, 'chief-of-staff'), ('lead', origin, 'lead')] + [('lead',Path(r['directory']),'lead') for r in recipients]
    for role, location, agent in locations:
        for ident, text in procedures(str(chief)).items():
            files[location / f'.opencode/skills/{ident}/SKILL.md'] = text
        from role_contract import agent as role_agent
        dispatcher = role_agent('dispatcher', str(Path.home()), str(chief))
        files[location / '.opencode/agents/heartbeat-pilot-dispatcher.md'] = dispatcher
        wrapper = (ROOT / 'heartbeat/watched.js').read_text()
        for name in ('plugin.mjs', 'chief.mjs', 'bus.mjs', 'paired-app.mjs', 'objective.mjs', 'attention.mjs', 'version.mjs'):
            wrapper = wrapper.replace("'./" + name + "'", repr(str(runtime / name)))
        wrapper = wrapper.replace('__OPTIONS_FILE__', str(options_path)).replace('__LOCATION__', str(location))
        wrapper = wrapper.replace('__STATUS_FILE__', str(location / '.opencode/reset-install/heartbeat-runtime.json'))
        wrapper += f'\n// watched activation phase: {phase}; options {hashlib.sha256(files[options_path].encode()).hexdigest()}\n'
        files[location / '.opencode/plugins/chief-heartbeat-pilot.js'] = wrapper
    DestinationRoot(Path.home()).validate_all(files)
    return chief, files


def canonical_policy(config, dry=False):
    """Migrate only the exact retired policy-file reference; never activate effects."""
    from urllib.parse import urlencode
    import sys
    home = Path.home(); chief = home / '.chief-of-staff'
    if config['chiefLocation'] != str(chief): raise ValueError('Existing owner Location required')
    options_path = chief / 'heartbeat/pilot-options.json'; raw = options_path.read_bytes(); options = json.loads(raw)
    old = chief / '.opencode/agents/chief-reset-staged-20261022-final.md'
    local = chief / '.opencode/agents/chief-of-staff.md'
    canonical = local if local.exists() else home / '.config/opencode/agents/chief-of-staff.md'
    DestinationRoot(home).validate_all([options_path, old, canonical])
    text = canonical.read_text(); body = agent_parts(text)[1]
    if MARK not in body or '; lean role' not in body:
        raise ValueError('Normally installed canonical lean chief role required')
    if options.get('chiefInstructionsFile') not in (str(old), str(canonical)):
        raise ValueError('Unexpected policy binding; preserve')
    sys.path.insert(0, config['docketSource'])
    from docket.host import configured_adapter
    adapter = configured_adapter()
    code, response = adapter._request('GET', '/api/agent/chief-of-staff?' + urlencode({'location[directory]':str(chief)}))
    if code != 200 or response.get('data', response).get('system', '').strip() != body.strip():
        raise ValueError('Canonical chief file does not match effective native role')
    updated = dict(options, chiefInstructionsFile=str(canonical))
    value = json.dumps(updated, indent=2) + '\n'
    # Discover executable/config references only; historical receipts/reports stay.
    references = []
    locations = {str(chief), *options.get('originDirectories', {}).values()}
    for directory in locations | {str(home / '.config/opencode')}:
        root = Path(directory) if directory == str(home / '.config/opencode') else Path(directory) / '.opencode'
        candidates = [root / 'opencode.json', root / 'opencode.jsonc', *(root / 'agents').glob('*.md'),
                      *(p for p in (root / 'plugins').rglob('*') if p.suffix in ('.js','.mjs','.ts','.json'))]
        for candidate in candidates:
            if candidate != old and candidate.is_file() and old.stem in candidate.read_text(): references.append(str(candidate))
    if str(old) in json.dumps({k:v for k,v in updated.items() if k != 'chiefInstructionsFile'}):
        references.append(str(options_path) + ' (another field)')
    old_bytes = old.read_bytes() if old.exists() else None
    if old_bytes is not None:
        installed = json.loads((chief / '.opencode/reset-install' / (old.stem + '.json')).read_text())
        if installed.get('state') != 'installed' or installed.get('files', {}).get(str(old)) != old_bytes.decode():
            raise ValueError('Exact staged bytes differ from normal installer receipt; preserve')
    code, response = adapter._request('GET','/api/session/active')
    if code != 200 or not isinstance(response.get('data'),dict):
        raise ValueError('Live session references unavailable; preserve staged file')
    for sid in response['data']:
        code, session = adapter._request('GET','/api/session/' + sid)
        if code != 200: raise ValueError('Live native identity unavailable; preserve staged file')
        if session.get('data',session).get('agent') == old.stem: references.append('active native session ' + sid)
    result = {'canonicalChiefInstructionsFile':str(canonical), 'otherLiveReferences':references,
              'retiredStagedFile':old_bytes is not None and not references, 'onlyOptionsFieldChanged':'chiefInstructionsFile'}
    if dry: print(json.dumps(result, indent=2)); return
    if options_path.read_bytes() != raw or canonical.read_text() != text:
        raise ValueError('Expected options/canonical role changed; no write')
    receipt = chief / 'archive/reset-policy-binding' / ('install-' + str(time.time_ns()) + '.json')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({'beforeOptions':options,'afterOptions':updated,**result},indent=2)+'\n')
    if options != updated:
        fd, temporary = tempfile.mkstemp(dir=options_path.parent, prefix='pilot-options.')
        try:
            os.fchmod(fd, options_path.stat().st_mode & 0o777)
            with os.fdopen(fd,'w') as out: out.write(value)
            if options_path.read_bytes() != raw: raise ValueError('Expected options changed; no replace')
            os.replace(temporary, options_path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    if json.loads(options_path.read_text()) != updated: raise ValueError('Canonical policy readback differs')
    if old_bytes is not None and not references:
        if old.read_bytes() != old_bytes: raise ValueError('Staged file changed; keep it')
        old.unlink()
    print(json.dumps(result, indent=2))


def maintain(config, dry=False):
    """Source-only upkeep of receipt-owned existing runtime; never generate options."""
    home = Path.home(); chief = home / '.chief-of-staff'
    if config['chiefLocation'] != str(chief):
        raise ValueError('maintenance requires the existing owner Location')
    options_path = chief / 'heartbeat/pilot-options.json'
    raw = options_path.read_bytes(); options = json.loads(raw)
    recipients = config.get('postOnlyRecipients', [])
    origins = {config['originSession']: config['originDirectory'], **{r['session']: r['directory'] for r in recipients}}
    expected = {'originDirectory': config['originDirectory'], 'originDirectories': origins,
                'originSessions': list(origins), 'goalSessions': [config['originSession']],
                'goalBindings': {config['originSession']: config['goalBinding']},
                'chiefPointerFile': str(chief / 'chief.json'), 'docketSource': config['docketSource']}
    if options.get('enabled') is not True or any(options.get(k) != v for k, v in expected.items()):
        raise ValueError('maintenance cannot enable or change existing topology/goal/options')
    if not options.get('holdBindings') or not options.get('deferInitialTick'):
        raise ValueError('existing hold bindings and no-startup-dispatch required')
    runtime = home / '.local/share/chief-of-staff/heartbeat'
    owned = {}
    for receipt in (chief / 'archive').glob('reset-*/install-*.json'):
        for target, digest in json.loads(receipt.read_text()).get('after', {}).items():
            if isinstance(digest, str): owned.setdefault(target, set()).add(digest)
    if not owned.get(str(options_path)):
        raise ValueError('existing opted-in owner receipt required')
    files = {runtime / p.name: p.read_text() for p in (ROOT / 'heartbeat').iterdir()
             if p.suffix in ('.mjs', '.py', '.js', '.json', '.md') and not p.name.endswith('.test.mjs')}
    roster = str(home / '.docket/lead-checkins.jsonl')
    if options.get('rosterFile', roster) != roster:
        raise ValueError('maintenance cannot replace roster binding')
    for location in dict.fromkeys([str(chief), *origins.values()]):
        directory = Path(location)
        if directory.resolve() != directory or not directory.is_dir():
            raise ValueError('existing canonical opted-in Location required')
        target = directory / '.opencode/plugins/chief-heartbeat-pilot.js'
        if not target.is_file() or not owned.get(str(target)):
            raise ValueError('maintenance cannot add a watched recipient')
        wrapper = (ROOT / 'heartbeat/watched.js').read_text()
        for name in ('plugin.mjs', 'chief.mjs', 'bus.mjs', 'paired-app.mjs', 'objective.mjs', 'attention.mjs', 'version.mjs'):
            wrapper = wrapper.replace("'./" + name + "'", repr(str(runtime / name)))
        wrapper = wrapper.replace('__OPTIONS_FILE__', str(options_path)).replace('__LOCATION__', location)
        wrapper = wrapper.replace('__STATUS_FILE__', str(directory / '.opencode/reset-install/heartbeat-runtime.json'))
        wrapper = wrapper.replace("const status = {", "// Installer-owned maintenance bindings; saved options remain byte-identical.\n    options.rosterFile ??= " + json.dumps(roster) + ";\n    options.reconciliationRequired = true;\n    const status = {")
        wrapper += '\n// maintenance options sha256: ' + sha256(raw) + '\n'
        files[target] = wrapper
        # Existing local procedures override global copies. Refresh only exact
        # receipt-owned existing exports; never enroll a missing local skill.
        for ident, text in procedures(str(chief)).items():
            procedure = directory / '.opencode/skills' / ident / 'SKILL.md'
            if procedure.exists() and procedure.read_text() != text:
                if not owned.get(str(procedure)):
                    raise ValueError('unowned local procedure; preserve: ' + str(procedure))
                files[procedure] = text
    DestinationRoot(home).validate_all(files)
    observed = {}
    for target, text in files.items():
        observed[target] = target.read_bytes() if target.exists() else None
        if observed[target] is not None and observed[target] != text.encode() and sha256(observed[target]) not in owned.get(str(target), set()):
            raise ValueError('owned runtime changed; preserve/reconcile: ' + str(target))
    if dry:
        print('\n'.join(str(p) for p in files)); return
    receipt = chief / 'archive/reset-runtime-maintenance' / ('install-' + str(time.time_ns()) + '.json')
    DestinationRoot(home).validate_all([receipt])
    before = {str(p): {'text': observed[p].decode(), 'mode': p.stat().st_mode & 0o777} if observed[p] is not None else None for p in files}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x') as out:
        json.dump({'phase': 'maintenance', 'optionsSha256': sha256(raw), 'before': before,
                   'after': {str(p): sha256(text.encode()) for p, text in files.items()}}, out, indent=2)
    if options_path.read_bytes() != raw:
        raise ValueError('owner options changed during preflight; no runtime writes')
    for target, text in sorted(files.items(), key=lambda pair: pair[0].parent.name == 'plugins'):
        current = target.read_bytes() if target.exists() else None
        if current != observed[target]: raise ValueError('owned export changed after preflight; preserve: ' + str(target))
        if current == text.encode(): continue
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
    if options_path.read_bytes() != raw:
        raise ValueError('owner options changed concurrently; inspect, never restore blindly')
    print('maintained existing runtime; options untouched; receipt ' + str(receipt))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run(config, phase, dry=False):
    if phase == 'canonical-chief':
        return canonical_policy(config, dry)
    if phase == 'maintenance':
        return maintain(config, dry)
    if not dry:
        raise ValueError('live heartbeat install blocked until full real-call fixture matrix passes')
    chief, files = plan(config, phase)
    if phase == 'attention':
        # Source maintenance for already opted-in recipients is not a migration.
        # Do not release/reconcile an active batch just to update this helper.
        path = chief/'heartbeat/pilot-options.json'
        prior, proposed = json.loads(path.read_text()), json.loads(files[path])
        for key in ('enabled','originSessions','originDirectories','goalSessions','goalBindings','holdBindings'):
            if prior.get(key) != proposed.get(key):
                raise ValueError('attention maintenance cannot change topology/goals/holds')
    revision = config.get('revision', '')
    if revision and not re.fullmatch(r'[a-z0-9-]{1,64}', revision): raise ValueError('simple explicit rollout revision required')
    if not dry and config.get('postOnlyRecipients'):
        # This guard is NOT run by read-only preparation. No candidate Location writes
        # until the specific real predecessor FYI has naturally been filed and is idle.
        gate = config['migrationGate']; rows = [json.loads(line) for line in (chief/'heartbeat/bus/events.jsonl').read_text().splitlines() if line]
        post = next(r for r in rows if r.get('type') == 'post' and r.get('id') == gate['event'])
        results = [r for r in rows if r.get('type') == 'result' and r.get('event') == gate['event']]
        active = None
        for row in rows:
            if row.get('type') == 'claim': active = row['id']
            if row.get('type') == 'finish' and row.get('batch') == active: active = None
        if (active and phase != 'attention') or post['urgency'] != 'fyi' or post['origin']['sessionID'] != gate['originSession'] or post['key'] != gate['key'] or not results or results[-1]['route'] != 'filed':
            raise ValueError('real predecessor FYI not naturally filed/idle; do not force it')
        import sys
        sys.path.insert(0, config['docketSource'])
        from docket.host import configured_adapter
        adapter = configured_adapter()
        for recipient in config['postOnlyRecipients']:
            status, response = adapter._request('GET', '/api/session/' + recipient['session'])
            native = response.get('data', {})
            if status != 200 or native.get('agent') != 'lead' or native.get('location',{}).get('directory') != recipient['directory'] or native.get('time',{}).get('archived'):
                raise ValueError('candidate native recipient/Location binding differs')
    if phase == 'roles' and not dry:
        pointer = json.loads((chief / 'chief.json').read_text())
        for location in (chief, Path(config['originDirectory']), *[Path(r['directory']) for r in config.get('postOnlyRecipients', [])]):
            status = json.loads((location / '.opencode/reset-install/heartbeat-runtime.json').read_text())
            if (not status.get('ready') or not status.get('enabled') or status.get('version') != config['nativeVersion']
                    or status.get('chief') != {'session': pointer['session'], 'directory': pointer['directory']}
                    or status.get('originSessions') != [config['originSession']] + [r['session'] for r in config.get('postOnlyRecipients', [])]
                    or len(status.get('registeredTools', [])) != 8 or status.get('lastError')):
                raise ValueError('prove enabled exact recipient/tool bindings before role override')
    receipt = chief / ('archive/reset-20261022-heartbeat/install-' + phase + ('-' + revision if revision else '') + '.json')
    DestinationRoot(Path.home()).validate_all([receipt])
    old_receipts = sorted(receipt.parent.glob('install-*.json'), key=lambda p:p.stat().st_mtime_ns) if receipt.parent.exists() else []
    owned = {p: value for r in old_receipts if r.is_file() for p,value in json.loads(r.read_text())['after'].items()}
    for target, text in files.items():
        if target.exists() and str(target) in owned and target.read_text() != text and hashlib.sha256(target.read_bytes()).hexdigest() != owned[str(target)]:
            raise ValueError('owned file changed since prior phase; preserve/reconcile: ' + str(target))
        if target.exists() and target.read_text() != text and str(target) not in owned and MARK not in target.read_text():
            raise ValueError('unowned pilot target: ' + str(target))
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved['after'] == {str(p): hashlib.sha256(t.encode()).hexdigest() for p,t in files.items()} and all(p.is_file() and p.read_text() == t for p,t in files.items()):
            print('same ' + phase + ' pilot'); return
        raise ValueError('retained phase receipt differs; reconcile rather than overwrite')
    if dry:
        print('\n'.join(str(p) for p in files)); return
    before = {str(p): {'text': p.read_text(), 'mode': p.stat().st_mode & 0o777} if p.exists() else None for p in files}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x') as out:
        json.dump({'phase': phase, 'before': before, 'after': {str(p): hashlib.sha256(t.encode()).hexdigest() for p,t in files.items()}}, out, indent=2); out.write('\n')
    # Sources/options first, watched entries next, scoped role overrides last.
    ordered = sorted(files, key=lambda p: (p.name in ('chief-of-staff.md','lead.md'), p.suffix == '.js'))
    for target in ordered:
        text = files[target]
        if target.exists() and target.read_text() == text: continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        if target.name == 'chief-nod': target.chmod(0o755)
        assert target.read_text() == text
    print('installed ' + phase + '; originals/absence/modes retained in ' + str(receipt))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path); ap.add_argument('phase', choices=('prepare','enable','roles','attention','maintenance','canonical-chief')); ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    try:
        config = json.loads(args.manifest.read_text())
        if 'base' in config:
            base = config.pop('base')
            if Path(base).name != base: raise ValueError('base profile must be a sibling filename')
            config = {**json.loads((args.manifest.parent/base).read_text()), **config}
        run(config, args.phase, args.dry_run)
    except (ValueError, OSError, KeyError) as e: raise SystemExit(str(e))
