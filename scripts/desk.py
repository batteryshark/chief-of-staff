#!/usr/bin/env python3
"""Local offline desk CLI. No command sends, authenticates or starts a service.

Admin commands require --operator to prevent accidental role use, NOT as an
authentication barrier. Broad local tools are not a sandbox. Host admission
must eventually use Store.receive with a separately proven verifier.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from desk_store import Store, atomic, guard, guarded_section, resolve_route, ident
from install_paths import DestinationRoot


def run(args, data):
    home = Path(args.home)
    if args.command == 'resolve':
        return resolve_route(home, data['project'], data['lead'])
    if args.command == 'render-pilot':
        # Source-only command; installed module does not contain the entire kit.
        try:
            from render import render
        except ImportError as error:
            raise ValueError('render-pilot is source-only; installed module does not contain the kit renderer') from error
        return render('hosts/opencode-lead.md', str(home), desk_project=ident(data['project']))
    admin = ('register', 'rule', 'route', 'decision', 'chief-section', 'brief-patch', 'delivery', 'canvas-result', 'knowledge-result')
    if args.command in admin and not args.operator:
        raise ValueError('trusted operator operation; not report/model authority')
    store = Store(home)
    try:
        command = args.command
        if command == 'file-report':
            return store.receive(data['report'], data['context'])  # ALWAYS unverified.
        if command == 'project':
            return store.project_files()
        if command == 'recover-delivery':
            store.recover_delivery()
            return {'state': 'uncertain; inspect native ids, never replay'}
        if command == 'audit':
            return {name: [dict(row) for row in store.db.execute('SELECT * FROM ' + name)]
                    for name in ('events', 'audit', 'outbox', 'changes')}
        if command == 'status':
            return {'watermark': store.watermark(), 'projected': store.meta('projected'),
                    'projection_error': store.meta('projection_error'),
                    'brief_pending': store.meta('brief_pending'), 'optional_canvas': store.projection(),
                    'knowledge': {name: store.knowledge_state(name) for name in store.registry.get('projects', {})}}
        if command == 'register':
            store.register(data['project'], data['path'], data['log'], data['leads'])
        elif command == 'rule':
            store.add_rule(data)
        elif command == 'route':
            name = ident(data['project'])
            project = store.project(name)
            path = home / 'desk/routes.json'
            DestinationRoot(home).validate_all([path])
            with guard(home):
                routes = json.loads(path.read_text())
                previous = routes['projects'].get(name, {'epoch': 0})
                if previous['epoch'] != data['expected_epoch'] or type(data['enabled']) is not bool:
                    raise ValueError('route epoch conflict')
                routes['projects'][name] = {'epoch': previous['epoch'] + 1, 'enabled': data['enabled'],
                    'leads': project['leads'], 'adoption': 'pending explicit native ACK and real report'}
                atomic(path, json.dumps(routes, indent=2) + '\n')
        elif command == 'decision':
            return store.decision_update(data['project'], data['expected_seq'], data['your_part'], data['reference'])
        elif command == 'chief-section':
            return guarded_section(home, data['section'], data['revision'], data['before'], data['after'])
        elif command == 'brief-patch':
            store.brief_patch(data['project'], data['revision'], data['before'], data['cells'])
        elif command == 'delivery':
            store.delivery(data['seq'], data['state'], data.get('message_id'), data.get('detail', ''))
        elif command == 'canvas-result':
            store.canvas_result(data['view_id'], data['expected_revision'], data['revision'], data['watermark'])
        elif command == 'knowledge-prepare':
            return store.knowledge_prepare(data['project'])
        elif command == 'knowledge-result':
            return store.knowledge_result(data['project'], data['intent'], data['state'], data.get('note_id'), data.get('body'))
        else:
            raise ValueError('unknown command')
        return {'recorded': True, 'sent': False}
    finally:
        store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', required=True)
    parser.add_argument('--operator', action='store_true')
    parser.add_argument('command', choices=['resolve', 'render-pilot', 'file-report', 'project',
        'recover-delivery', 'audit', 'status', 'register', 'rule', 'route', 'decision',
        'chief-section', 'brief-patch', 'delivery', 'canvas-result', 'knowledge-prepare', 'knowledge-result'])
    # Knowledge is the primary projection; optional Canvas remains a staged gap.
    args = parser.parse_args()
    try:
        data = json.load(sys.stdin) if args.command not in ('audit', 'status', 'project', 'recover-delivery') else {}
        print(json.dumps(run(args, data), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as e:
        sys.exit(f'desk: {e}')
