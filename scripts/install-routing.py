"""Install owned routing exports; optional native dispatch needs explicit owner bindings."""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from install_paths import DestinationRoot

MARKER = 'managed by chief-of-staff runway installer'


def absolute(value):
    path = Path(value)
    if not path.is_absolute() or str(path.resolve()) != value:
        raise ValueError('Existing canonical absolute binding required: ' + value)
    return path


def dispatch_options(options, location):
    allowed = {'chiefPointerFile', 'rosterFile', 'holdBindings', 'workerAgent', 'lane', 'completionTimeoutMs'}
    if not isinstance(options, dict) or set(options) - allowed:
        raise ValueError('Only explicit production hostDispatch bindings are accepted; no credentials/fixtureMode')
    if not any(options.get(k) for k in ('chiefPointerFile', 'rosterFile')):
        raise ValueError('Current chief pointer and/or enrolled roster required')
    for key in ('chiefPointerFile', 'rosterFile'):
        if key in options and not absolute(options[key]).is_file():
            raise ValueError('Current identity binding file required')
    if 'chiefPointerFile' in options:
        pointer = json.loads(Path(options['chiefPointerFile']).read_text())
        if not re.fullmatch(r'ses_[A-Za-z0-9]+', pointer.get('session', '')) or pointer.get('directory') != str(location):
            raise ValueError('Chief pointer must identify this exact native Location')
    if 'workerAgent' in options and not re.fullmatch(r'[A-Za-z0-9_-]+', options['workerAgent']):
        raise ValueError('Explicit authorized worker agent required')
    timeout = options.get('completionTimeoutMs', 25000)
    if type(timeout) is not int or not 0 < timeout <= 60000:
        raise ValueError('Completion timeout must be 1..60000 ms')
    bindings = options.get('holdBindings')
    if not isinstance(bindings, dict) or str(location) not in bindings:
        raise ValueError('Current project hold section must be explicitly bound')
    for directory, binding in bindings.items():
        if not absolute(directory).is_dir(): raise ValueError('Existing hold Location required')
        if isinstance(binding, list):
            specs = binding
        elif isinstance(binding, dict) and options.get('lane') in binding.get('lanes', {}):
            specs = binding.get('global', []) + binding['lanes'][options['lane']]
        else:
            raise ValueError('Applicable hold lane/sections required')
        if not specs: raise ValueError('Nonempty hold sections required')
        for spec in specs:
            if set(spec) != {'file', 'heading', 'allowedQuote'}:
                raise ValueError('Exact file/heading/allowedQuote required')
            lines = absolute(spec['file']).read_text().splitlines()
            heading = spec['heading']; quote = spec['allowedQuote']
            if not re.match(r'^#+ ', heading) or not quote.strip() or heading not in lines:
                raise ValueError('Current exact hold section required')
            start = lines.index(heading) + 1; level = len(heading.split(' ')[0]); end = start
            while end < len(lines) and not re.match(r'^#{1,' + str(level) + r'} ', lines[end]): end += 1
            if '\n'.join(lines[start:end]).strip() != quote.strip():
                raise ValueError('Current hold differs; never refresh an allowed quote automatically')
    return options


def install(src, mode, manifest=None):
    if mode not in ('install', 'dry'):
        raise ValueError('Routing installation supports install or --dry-run only')
    home = Path.home(); config_path = home / '.config/opencode/opencode.json'; output = src / 'dist'
    options = None
    if manifest is not None:
        if set(manifest) - {'location', 'pluginRoot', 'hostDispatch'} or 'location' not in manifest or 'hostDispatch' not in manifest:
            raise ValueError('Dispatch manifest requires location + hostDispatch only (optional pluginRoot)')
        location = absolute(manifest['location'])
        if not location.is_dir(): raise ValueError('Existing native Location required')
        config_path = location / '.opencode/opencode.json'
        if (location / 'opencode.jsonc').exists(): raise ValueError('Preserve existing JSONC; reconcile explicitly')
        if 'pluginRoot' in manifest:
            output = absolute(manifest['pluginRoot'])
            if not output.is_relative_to(location): raise ValueError('Scoped build must stay inside its native Location')
        options = dispatch_options(manifest['hostDispatch'], location)
    if config_path.with_suffix('.jsonc').exists():
        raise ValueError('Existing JSONC configuration; JSON will not be created alongside it')
    if not (output / 'package.json').exists() or not (output / 'index.js').is_file():
        raise ValueError('Build routing first: node scripts/build.mjs [dedicated output directory]')
    if json.loads((output / 'package.json').read_text()).get('name') != 'chief-runway-opencode':
        raise ValueError('Owned routing build required')
    DestinationRoot(home).validate_all([config_path])
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    if manifest is not None and output != src / 'dist':
        # Isolate the explicitly selected scoped build from the already loaded
        # global build with the same plugin ID. Never modify global policy.
        policies = config.setdefault('policies', [])
        if not isinstance(policies, list): raise ValueError('Existing policies must be preserved as a list')
        for target in (src / 'dist', src / 'dist/index.js'):
            rule = {'action':'integration.use','resource':'plugin:' + str(target),'effect':'deny'}
            if rule not in policies: policies.append(rule)
    plugins = config.setdefault('plugins', [])
    if not isinstance(plugins, list): raise ValueError('OpenCode plugins is not a list')
    plugin = output.as_uri()
    matches = [i for i, p in enumerate(plugins) if (p if isinstance(p, str) else p.get('package')) in (plugin, str(output), str(output / 'index.js'))]
    if len(matches) > 1: raise ValueError('Ambiguous existing routing entries; preserve/reconcile')
    if options is not None:
        prior = plugins[matches[0]] if matches else {}
        prior_options = prior.get('options', {}) if isinstance(prior, dict) else {}
        entry = {'package': plugin, 'options': {**prior_options, 'hostDispatch': options}}
        if matches: plugins[matches[0]] = entry
        else: plugins.append(entry)
    elif not matches:
        plugins.append(plugin)
    files = {config_path: (json.dumps(config, indent=2) + '\n', 0o600)}
    if manifest is None:
        launcher = home / '.local/bin/chief-runway'
        if launcher.exists() and (launcher.is_symlink() or MARKER not in launcher.read_text()):
            raise ValueError('Existing chief-runway is not managed by this installer')
        text = '#!/usr/bin/env python3\n# ' + MARKER + '\nimport runpy, sys\nsys.path.insert(0, ' + repr(str(src)) + ')\nrunpy.run_path(' + repr(str(src / 'runway_main.py')) + ", run_name='__main__')\n"
        files[launcher] = (text, 0o755)
        routes = Path(os.environ.get('CHIEF_RUNWAY_HOME', '~/.chief-of-staff/runway')).expanduser() / 'routes.json'
        if not routes.exists(): files[routes] = ((src / 'routing/routes.example.json').read_text(), 0o600)
    DestinationRoot(home).validate_all(files)
    for path, (value, permissions) in files.items():
        if mode == 'dry': print('update', path); continue
        if path.exists() and path.read_text() == value: continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
        try:
            os.fchmod(fd, path.stat().st_mode & 0o777 if path.exists() else permissions)
            with os.fdopen(fd, 'w') as out: out.write(value)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    print('Routing installed.' if mode == 'install' else 'Routing dry run complete.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path); parser.add_argument('mode', choices=('install', 'dry'))
    parser.add_argument('--dispatch-config', type=Path)
    args = parser.parse_args()
    try:
        install(args.source.resolve(), args.mode, json.loads(args.dispatch_config.read_text()) if args.dispatch_config else None)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error))
