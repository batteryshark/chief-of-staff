#!/usr/bin/env python3
"""Stage normal role output only in an explicitly repair-owned throwaway root.

No live application mode exists until the full real-call matrix is green.
"""
import argparse
import json
from pathlib import Path
import sys
import hashlib
from role_contract import agent, canonical, knowledge_plans, project_config, authorized_project_docs, MARK

REPAIR = Path('/example/home/Projects/workstack/system-repair').resolve()


def stage(root, locations, native_local=False, cleanup=None, milestone_sessions=(), docket_source=None,
          chief_locations=(), chief_project_sessions=(), chief_rollout_roster=None):
    root = Path(canonical(str(root)))
    if root.parent != REPAIR / 'fixtures' or not root.is_dir():
        raise ValueError('existing direct repair fixtures child required; never a live install')
    home = root / 'home'; brief = home / '.chief-of-staff'
    project_docs = []
    if chief_project_sessions:
        roster = Path(canonical(str(chief_rollout_roster)))
        if not roster.is_relative_to(root) or not docket_source:
            raise ValueError('owned fixture enrollment and existing native adapter required')
        rows = [json.loads(line) for line in roster.read_text().splitlines() if line.strip()]
        sys.path.insert(0, str(Path(canonical(str(docket_source)))))
        from docket.host import configured_adapter
        sessions = []
        for sid in chief_project_sessions:
            status, response = configured_adapter()._request('GET', '/api/session/' + sid)
            session = response.get('data', response)
            if status != 200 or session.get('id') != sid:
                raise ValueError('native project identity unavailable')
            directory = Path(canonical(session['location']['directory']))
            if not directory.is_relative_to(REPAIR / 'fixtures'):
                raise ValueError('only owned fixture project targets allowed')
            sessions.append(session)
        project_docs = authorized_project_docs(rows, sessions)
    files = {}
    for role, name in (('chief', 'chief-of-staff'), ('lead', 'lead'), ('dispatcher', 'heartbeat-pilot-dispatcher')):
        files[home / f'.config/opencode/agents/{name}.md'] = agent(role, str(home), str(brief), project_docs if role == 'chief' else ())
    if milestone_sessions:
        if not docket_source:
            raise ValueError('existing Docket source required for shared writer')
        source = Path(canonical(str(docket_source)))
        sys.path.insert(0, str(source))
        from docket.host import configured_adapter
        adapter = configured_adapter()
        callers = []
        for sid in milestone_sessions:
            status, response = adapter._request('GET', '/api/session/' + sid)
            session = response.get('data', response)
            directory = session.get('location', {}).get('directory', '')
            if (status != 200 or session.get('id') != sid or session.get('agent') != 'lead'
                    or Path(directory) not in locations or session.get('time', {}).get('archived')):
                raise ValueError('native fixture lead identity required')
            callers.append(dict(sessionID=sid, agentID='lead', directory=directory))
        runtime = home / '.config/opencode/plugins'
        kit = Path(__file__).resolve().parents[1]
        for name in ('shared.js', 'milestone.mjs'):
            files[runtime / ('own-milestone.js' if name == 'shared.js' else name)] = (kit / 'services/docket' / name).read_text()
        helpers = ['docket/milestone.py', 'docket/checkins.py', 'docket/parse.py', 'docket/__init__.py']
        binding = dict(pythonPath='/usr/bin/python3', sourceRoot=str(source), home=str(home), callers=callers,
                       sourceHashes={p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in helpers})
        files[runtime / 'binding.json'] = json.dumps(binding, indent=2) + '\n'
        if native_local:
            for path, text in list(files.items()):
                if path.parent == runtime:
                    files[root / '.opencode/plugins' / path.name] = text
    for location in locations:
        location = Path(canonical(str(location)))
        if not location.is_relative_to(root) or location == root:
            raise ValueError('fixture Location must be inside owned root')
        # Real project Knowledge only; no manifest plan path override.
        plans = knowledge_plans(str(location), str(Path.home()))
        path = location / '.opencode/opencode.json'
        if path.with_suffix('.jsonc').exists():
            raise ValueError('JSONC config requires explicit reconciliation; no shadow config')
        old = json.loads(path.read_text()) if path.exists() else {}
        files[path] = json.dumps(project_config(old, 'lead', str(home), str(brief), str(location), plans), indent=2) + '\n'
        if native_local:
            # Existing host cannot change its global config without a reload. These
            # fixture-only copies are BYTE-IDENTICAL normal global output, no proof agents.
            for target, text in list(files.items()):
                if target.parent == home / '.config/opencode/agents':
                    files[root / '.opencode/agents' / target.name] = text
    for location in chief_locations:
        location = Path(canonical(str(location)))
        if not location.is_relative_to(root):
            raise ValueError('chief fixture Location outside root')
        path = location / '.opencode/opencode.json'
        old = json.loads(files[path]) if path in files else json.loads(path.read_text()) if path.exists() else {}
        files[path] = json.dumps(project_config(old, 'chief', str(home), str(brief), str(location), [], project_docs), indent=2) + '\n'
    if native_local:
        for target, text in list(files.items()):
            if target.parent == home / '.config/opencode/agents':
                files[root / '.opencode/agents' / target.name] = text
    # Preflight every write; a managed marker is not sufficient to overwrite custom globals.
    for path, text in files.items():
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('symlink fixture target')
        if path.exists() and path.suffix == '.md' and path.read_text() != text:
            raise ValueError('existing fixture role differs; use a fresh owned fixture')
    if cleanup:
        from role_cleanup import retire
        for directory, known_owned in cleanup.items():
            target = Path(canonical(directory))
            if not target.is_relative_to(root):
                raise ValueError('cleanup outside fixture refused')
            retire(target, known_owned, dry=True)
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    if cleanup:
        from role_cleanup import retire
        for directory, known_owned in cleanup.items():
            target = Path(canonical(directory))
            if not target.is_relative_to(root):
                raise ValueError('cleanup outside fixture refused')
            retire(target, known_owned)
    (brief / 'handoff').mkdir(parents=True, exist_ok=True)
    print(json.dumps({'fixture': str(root), 'files': [str(p) for p in files],
                      'nativeMatrix': 'NOT RUN', 'liveInstall': 'BLOCKED'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--location', action='append', type=Path, default=[])
    parser.add_argument('--native-local', action='store_true')
    parser.add_argument('--cleanup', type=Path, help='exact known-owned executable hashes only')
    parser.add_argument('--milestone-session', action='append', default=[])
    parser.add_argument('--docket-source', type=Path)
    parser.add_argument('--chief-location', action='append', type=Path, default=[])
    parser.add_argument('--chief-project-session', action='append', default=[])
    parser.add_argument('--chief-rollout-roster', type=Path)
    args = parser.parse_args()
    try:
        stage(args.root, args.location, args.native_local,
              json.loads(args.cleanup.read_text()) if args.cleanup else None,
              args.milestone_session, args.docket_source, args.chief_location,
              args.chief_project_session, args.chief_rollout_roster)
    except (ValueError, OSError, KeyError) as error:
        sys.exit(str(error))
