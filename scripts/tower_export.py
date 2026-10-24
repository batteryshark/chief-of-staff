"""Manual, explicit-allowlist Tower projection refresh; never a discovery daemon."""
import argparse
import json
import os
import re
import stat
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import tower_schema as schema

LIMIT = 512 * 1024
DENIED = re.compile(r'secret|credential|token|auth|password|(^|[._-])key([._-]|$)', re.I)
SECRET = re.compile(r'-----BEGIN .*PRIVATE KEY|\b(?:sk-|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{12,}|\bBearer\s+\S+|(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*\S+', re.I)


def sanitize(value):
    # Refuse rather than silently edit operational evidence or partially export secrets.
    if type(value) is str and SECRET.search(value):
        raise ValueError('private content rejected')
    for child in value.values() if type(value) is dict else value if type(value) is list else []:
        sanitize(child)


def root(value):
    p = Path(schema.text(value, 4096))
    home = Path.home()
    broad = {home, *home.parents, *(home / name for name in ('Projects','Downloads','Documents','.config','.chief-of-staff'))}
    if (not p.is_absolute() or p.resolve() != p or p in broad
            or any(DENIED.search(s) or '%' in s or '\\' in s for s in p.parts)):
        raise ValueError('explicit canonical scoped root required')
    return p


def relative(value, suffixes):
    schema.text(value, 4096)
    p = Path(value)
    if (p.is_absolute() or str(p) != value or p.suffix.lower() not in suffixes
            or any(c in value for c in ('%', '\\')) or any(s.startswith('.') or DENIED.search(s) for s in p.parts)):
        raise ValueError('path rejected')
    return p


def directory_fd(value):
    p = root(value)
    # Operator controls root ancestry; no claim of resistance to hostile root owners.
    return os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def parent_fd(base, rel):
    fd = directory_fd(base)
    try:
        for component in rel.parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except Exception:
        os.close(fd); raise


def read_exact(base, name, suffixes={'.md'}):
    rel = relative(name, suffixes); fd = parent_fd(base, rel)
    try:
        f = os.open(rel.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(f, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
                raise ValueError('not a bounded regular file')
            data = stream.read(LIMIT + 1)
            if len(data) > LIMIT: raise ValueError('file bound')
            return data
    finally:
        os.close(fd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('redirect refused')


def knowledge_read(directory, env=None, opener=None):
    env = os.environ if env is None else env
    url, token, caller = (env.get(k) for k in ('OPENCHAMBER_AGENT_TOOL_URL','OPENCHAMBER_AGENT_TOOL_TOKEN','OPENCODE_SESSION_ID'))
    if not url or not token or not caller or not re.fullmatch(r'ses_[A-Za-z0-9_-]+', caller):
        raise ValueError('inherited caller/auth unavailable')
    u = urlsplit(url)
    if u.scheme not in ('http','https') or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password or u.fragment:
        raise ValueError('loopback transport required')
    payload = {'tool':'openchamber_knowledge','sessionID':caller,'input':{'action':'knowledge.list','directory':directory}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST', headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with client.open(req, timeout=5) as response:
        raw = response.read(LIMIT+1)
        if len(raw) > LIMIT: raise ValueError('response bound')
    value = json.loads(raw)
    if type(value) is not dict or type(value.get('schemaVersion')) is not int or value['schemaVersion'] != 1 or value.get('ok') is not True or value.get('action') != 'knowledge.list' or type(value.get('data')) is not dict:
        raise ValueError('invalid Knowledge envelope')
    schema.depth(value)
    return value['data']


def configuration(config):
    schema.obj(config, 'version projects')
    if type(config.get('version')) is not int or config['version'] != 1: raise ValueError('invalid config')
    seen = set(); targets = set()
    for row in schema.seq(config.get('projects'), 100):
        schema.obj(row, 'project knowledge summary activity acceptance_request_id')
        p = schema.obj(row.get('project'), 'id title root outcome_id status header_file files images export')
        pid = schema.ident(p.get('id')); schema.ident(p.get('outcome_id')); schema.text(p.get('title'), 200); schema.text(p.get('status'), 80)
        if pid in seen: raise ValueError('duplicate project')
        seen.add(pid); root(p.get('root'))
        for group in ('files','images'):
            ids = set()
            for f in schema.seq(p.get(group, []), 100):
                schema.obj(f, 'id label root path' if group == 'files' else 'id path')
                fid = schema.ident(f.get('id'))
                if fid in ids or fid == 'knowledge': raise ValueError('duplicate/reserved file')
                ids.add(fid)
                if group == 'files': schema.text(f.get('label'),200)
                base = f.get('root', p['root']); root(base)
                relative(f.get('path'), {'.md'} if group == 'files' else {'.png','.jpg','.jpeg','.gif','.webp'})
            if group == 'files' and 'header_file' in p and p['header_file'] not in ids:
                raise ValueError('header not allowlisted')
        target = schema.obj(p.get('export'), 'root path'); root(target.get('root')); relative(target.get('path'), {'.json'})
        destination = (target['root'], target['path'])
        if destination in targets: raise ValueError('duplicate export destination')
        targets.add(destination)
        selected = set()
        for k in schema.seq(row.get('knowledge', []),200):
            schema.obj(k, 'id kind title file_id')
            iid = schema.ident(k.get('id')); schema.text(k.get('title'),200)
            if iid in selected or k.get('kind') not in ('note','todo','plan'): raise ValueError('invalid Knowledge allowlist')
            selected.add(iid)
            if k['kind'] == 'plan' and k.get('file_id') not in {f['id'] for f in p.get('files', [])}:
                raise ValueError('plan file not approved')
            if k['kind'] != 'plan' and 'file_id' in k: raise ValueError('unexpected file binding')
        if 'acceptance_request_id' in row: schema.ident(row['acceptance_request_id'])
    return config


def project_knowledge(row, reader=knowledge_read):
    try:
        data = reader(row['project']['root']); items = []
        for spec in row.get('knowledge', []):
            group = data.get({'note':'notes','todo':'todos','plan':'plans'}[spec['kind']])
            if type(group) is not list: raise ValueError('missing group')
            matches = [r for r in group if type(r) is dict and r.get('id') == spec['id']]
            if len(matches) != 1: raise ValueError('item absent or ambiguous')
            item = matches[0]
            out = {k:spec[k] for k in ('id','kind','title')}
            if spec['kind'] == 'plan':
                f = next(f for f in row['project']['files'] if f['id'] == spec['file_id'])
                base = f.get('root', row['project']['root'])
                if item.get('path') != str(Path(base) / f['path']): raise ValueError('native plan path mismatch')
                out['body'] = read_exact(base, f['path']).decode('utf-8')
            else:
                out['body'] = schema.text(item.get('text' if spec['kind'] == 'todo' else 'body'), 50000, True)
                if spec['kind'] == 'todo':
                    if type(item.get('completed')) is not bool: raise ValueError('invalid native todo')
                    out['completed'] = item['completed']
            sanitize(out); items.append(out)
        return {'state':'available','provenance':'OpenChamber Knowledge API','items':items,
                'observed_at':datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {'state':'unavailable','provenance':'OpenChamber Knowledge API unavailable or approved items invalid'}


def acceptance_read(rid):
    # Fixed installed helper; no caller-selected executable, state file or private ledger scrape.
    cli = str(Path.home()/'.local/bin/chief-nod')
    env = dict(os.environ)
    env.pop('CHIEF_NOD_STATE_DIR', None)
    result = subprocess.run([cli,'acceptance-status',rid], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=True)
    if len(result.stdout) > 32768: raise ValueError('acceptance bound')
    return json.loads(result.stdout)


def build(row, reader=knowledge_read, acceptance=acceptance_read):
    p = row['project']
    out = {'version':1,'project_id':p['id'],'outcome_id':p['outcome_id'],
           'knowledge':project_knowledge(row, reader)}
    for k in ('summary','activity'):
        if k in row: out[k] = row[k]
    if 'acceptance_request_id' in row:
        out['acceptance'] = acceptance(row['acceptance_request_id'])
    out['generated_at'] = datetime.now(timezone.utc).isoformat()
    schema.projection(out, p['id'], p['outcome_id']); sanitize(out)
    return out


def atomic_write(target, value):
    sanitize(value)
    raw = (json.dumps(value, ensure_ascii=False, separators=(',',':'))+'\n').encode()
    atomic_bytes(target, raw, {'.json'})


def atomic_bytes(target, raw, suffixes):
    if len(raw) > LIMIT: raise ValueError('projection bound')
    rel = relative(target['path'], suffixes); fd = parent_fd(target['root'], rel)
    name = None
    try:
        try:
            info = os.stat(rel.name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise ValueError('unsafe target')
        except FileNotFoundError: pass
        # Directory descriptor pins the reviewed destination, including temp/rename/fsync.
        import secrets
        name = '.tower-'+secrets.token_hex(16)
        tmp = os.open(name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(tmp,'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, rel.name, src_dir_fd=fd, dst_dir_fd=fd); name = None; os.fsync(fd)
    finally:
        if name is not None: os.unlink(name, dir_fd=fd)
        os.close(fd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
                                 epilog='Example: python3 -B tower_export.py /approved/export-config.json')
    ap.add_argument('--version', action='version', version='Tower projection exporter v1')
    ap.add_argument('config', help='exact approved project/item allowlist JSON file'); args = ap.parse_args()
    config = Path(args.config)
    rows = configuration(json.loads(read_exact(str(config.parent), config.name, {'.json'})))['projects']
    # Build/validate everything before writing any projection; each replace is atomic.
    ready = [(row['project']['export'], build(row)) for row in rows]
    for target, value in ready: atomic_write(target, value)
    print(json.dumps({'version':1,'exported':len(ready)}))


if __name__ == '__main__':
    try: main()
    except Exception: raise SystemExit('Tower export refused; inspect approved configuration privately')
