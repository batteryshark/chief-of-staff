"""Install only owned routing files; preserve unrelated OpenCode settings."""
import json
import os
import sys
import tempfile
from pathlib import Path

src, mode = Path(sys.argv[1]).resolve(), sys.argv[2]
marker = 'managed by chief-of-staff runway installer'
if mode not in ('install','dry'):
    raise SystemExit('Routing installation supports install or --dry-run; remove its plugin entry explicitly to disable.')
built = src/'dist/package.json'
if not built.exists():
    raise SystemExit('Build routing first: npm ci && npm run build')
config_path = Path.home()/'.config/opencode/opencode.json'
if not config_path.exists() and config_path.with_suffix('.jsonc').exists():
    raise SystemExit('Existing JSONC configuration: add the dist plugin URL there; JSON will not be created alongside it.')
config = json.loads(config_path.read_text()) if config_path.exists() else {}
plugin = (src/'dist').as_uri()
plugins = config.setdefault('plugins', [])
if not isinstance(plugins,list):
    raise SystemExit('OpenCode plugins is not a list')
if plugin not in plugins:
    plugins.append(plugin)
launcher = Path.home()/'.local/bin/chief-runway'
if launcher.exists() and (launcher.is_symlink() or marker not in launcher.read_text()):
    raise SystemExit('Existing chief-runway is not managed by this installer')
root = Path(os.environ.get('CHIEF_RUNWAY_HOME', '~/.chief-of-staff/runway')).expanduser()
routes = root/'routes.json'
def entry(script):
    return '#!/usr/bin/env python3\n# '+marker+'\nimport runpy, sys\nsys.path.insert(0, '+repr(str(src))+')\nrunpy.run_path('+repr(str(src/script))+", run_name='__main__')\n"
content = entry('runway_main.py')

def write(path, value, permissions=0o600):
    if mode=='dry':
        print('update',path);return
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        os.fchmod(fd,permissions)
        with os.fdopen(fd,'w') as f:f.write(value)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

write(config_path,json.dumps(config,indent=2)+'\n')
write(launcher,content,0o755)
if not routes.exists():
    write(routes,(src/'routing/routes.example.json').read_text())
print('Routing installed.' if mode=='install' else 'Routing dry run complete.')
