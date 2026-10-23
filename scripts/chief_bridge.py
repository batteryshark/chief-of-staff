"""Finite, opt-in chief bridge deployment. No role, service or global config writes."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'kits/chief/bridge.lock.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def safe(path, *, owned=True):
    """Reject symlinks in every component, foreign-owned targets and hard links."""
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        if item.is_symlink():
            raise ValueError(f'symlink refused: {item}')
    if path.exists():
        st = path.stat()
        if owned and st.st_uid != os.getuid():
            raise ValueError(f'foreign ownership: {path}')
        if path.is_file() and st.st_nlink != 1:
            raise ValueError(f'hard link refused: {path}')
    return path


def create(path, data):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as out:
        os.chmod(path, 0o600)
        out.write(data)


def run(args, cwd=None, timeout=600, env=None):
    try:
        result = subprocess.run([str(a) for a in args], cwd=cwd, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f'bounded command timed out after {timeout}s: {args[0:3]}') from exc
    if result.returncode:
        raise ValueError(f'{args[0:3]} failed: {result.stderr[-3000:]}{result.stdout[-3000:]}')
    return result.stdout.strip()


def git(repo, *args):
    return run(['git', '-c', 'core.hooksPath=/dev/null', '-C', repo, *args], timeout=90)


def lockfile(path=LOCK):
    lock = load(path)
    for key in ('commit', 'tree'):
        if not re.fullmatch('[0-9a-f]{40}', lock[key]):
            raise ValueError('real source pin required')
    if not re.fullmatch('[0-9a-f]{64}', lock['bun_lock_sha256']):
        raise ValueError('dependency integrity required')
    if lock['sdk'] != '0.3.224' or lock['options'] != {
        'routing': 'overlay', 'systemPrompt': {'agent': 'chief-of-staff', 'source': 'agent'}}:
        raise ValueError('unreviewed SDK/options')
    return lock


def source_check(repo, lock):
    if git(repo, 'rev-parse', 'HEAD') != lock['commit']:
        raise ValueError('source HEAD differs from locked commit')
    if git(repo, 'rev-parse', 'HEAD^{tree}') != lock['tree']:
        raise ValueError('source tree differs from lock')
    if git(repo, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('source must be clean (including untracked files)')
    if digest((repo / 'bun.lock').read_bytes()) != lock['bun_lock_sha256']:
        raise ValueError('frozen dependency integrity mismatch')
    git(repo, 'merge-base', '--is-ancestor', lock['upstream']['base'], lock['commit'])


def clone_source(destination, lock, source_repo=None):
    source = lock['repository']
    if source_repo is not None:
        source = safe(source_repo)
        if not source.is_dir():
            raise ValueError('local source must be an owned repository')
        source_check(source, lock)
    run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--no-local', '--no-checkout',
         '--', source, destination], timeout=90)
    try:
        git(destination, 'checkout', '--detach', lock['commit'])
    except ValueError as exc:
        raise ValueError('locked revision unavailable; publish approved branch or provide verified --source-repo') from exc
    source_check(destination, lock)


def dist_hash(repo):
    files = sorted((repo / 'dist').rglob('*'))
    if not (repo / 'dist/index.js').is_file():
        raise ValueError('missing built dist/index.js')
    h = hashlib.sha256()
    for file in files:
        if file.is_symlink():
            raise ValueError('symlink in dist')
        if file.is_file():
            h.update(str(file.relative_to(repo)).encode() + b'\0' + file.read_bytes() + b'\0')
    return h.hexdigest()


def build(repo, lock, bun):
    """No npm resolution or prepublishOnly. All tests are offline; never test:haiku."""
    if not bun:
        raise ValueError('existing Bun required for candidate build; supply --bun')
    bun = shutil.which(str(bun)) or str(bun)
    # Upstream smoke spawns bare `bun`. Scope PATH to build/test children only,
    # never mutate this process or the host's environment.
    env = {**os.environ, 'PATH': str(Path(bun).absolute().parent) + os.pathsep + os.environ.get('PATH', '')}
    before = (repo / 'bun.lock').read_bytes()
    run([bun, 'install', '--frozen-lockfile', '--ignore-scripts'], repo, env=env)
    sdk = load(repo / 'node_modules/@anthropic-ai/claude-agent-sdk/package.json')['version']
    if sdk != lock['sdk'] or before != (repo / 'bun.lock').read_bytes():
        raise ValueError('SDK version or frozen lock changed')
    run([bun, 'run', 'build'], repo, env=env)
    # The upstream runner uses Bun subprocesses, not live inference.
    tests = run([bun, 'test/run.ts'], repo, env=env)
    return {'sdk': sdk, 'dist_sha256': dist_hash(repo), 'tests': tests,
            'bun': str(bun), 'bun_version': run([bun, '--version'])}


def prepare(managed, lock, bun, source_repo=None):
    managed = safe(managed)
    revisions = safe(managed / 'revisions')
    target = safe(revisions / lock['commit'])
    if target.exists():
        return verified(target, lock)
    revisions.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.prepare-', dir=revisions))
    repo = stage / 'source'
    # Failures are retained for diagnosis, never substituted for a ready revision.
    clone_source(repo, lock, source_repo)
    result = build(repo, lock, bun)
    result.update({'version': 1, 'commit': lock['commit'], 'lock_sha256': digest(encoded(lock)),
                   'origin': str(source_repo or lock['repository'])})
    create(repo / '.chief-ready.json', encoded(result))
    repo.rename(target)
    stage.rmdir()
    return verified(target, lock)


def verified(repo, lock):
    repo = safe(repo)
    receipt = load(safe(repo / '.chief-ready.json'))
    if (receipt['commit'] != lock['commit'] or receipt['lock_sha256'] != digest(encoded(lock))
            or receipt['dist_sha256'] != dist_hash(repo)
            or digest((repo / 'bun.lock').read_bytes()) != lock['bun_lock_sha256']
            or load(repo / 'node_modules/@anthropic-ai/claude-agent-sdk/package.json')['version'] != lock['sdk']
            or git(repo, 'rev-parse', 'HEAD^{tree}') != lock['tree']
            or git(repo, 'diff', 'HEAD', '--')):
        raise ValueError('prepared revision changed or belongs to another lock')
    return {**receipt, 'directory': str(repo), 'package': str(repo / 'dist')}


def runtime_receipt(repo):
    """Version probes only, using exactly the fork resolver; not a model request."""
    script = '''import {resolveClaudeCodeExecutable,runCliProbe} from './dist/executable-path.js';
const path = await resolveClaudeCodeExecutable();
const probe = path ? await runCliProbe(path, ['--version'], {timeoutMs:4000}) : null;
console.log(JSON.stringify({path, version:probe?.stdout.trim() || null,
  fallback:path === null ? 'SDK bundled executable (host must verify actual path/version)' : null,
  scope:'preparation shell environment; host environment may resolve differently'}));'''
    return json.loads(run(['node', '--input-type=module', '-e', script], repo, timeout=45))


def delta(target, after, kind, **metadata):
    target = safe(target)
    before = target.read_bytes()
    return {'version': 1, 'kind': kind, 'target': str(target), 'uid': os.getuid(),
            'before': base64.b64encode(before).decode(), 'after': base64.b64encode(after).decode(),
            'before_sha256': digest(before), 'after_sha256': digest(after), **metadata}


def bridge_plan(config, revision, lock, previous=None):
    config = safe(config)
    # Explicit chief-local path only; never accept a generic/global config target.
    if config.name != 'opencode.json' or config.parent.name != '.opencode' or config.parent.parent.name != '.chief-of-staff':
        raise ValueError('target must be chief-local .chief-of-staff/.opencode/opencode.json')
    ready = verified(revision, lock)
    data = load(config)  # JSONC refused rather than silently stripping comments/policies.
    plugins = data.get('plugins', [])
    if not isinstance(plugins, list):
        raise ValueError('plugins must be an array')
    entry = {'package': ready['package'], 'options': lock['options']}
    old_entry = None
    if previous:
        previous = load(safe(previous))
        if previous['kind'] != 'bridge' or previous['uid'] != os.getuid() or previous['target'] != str(config) or digest(config.read_bytes()) != previous['after_sha256']:
            raise ValueError('previous ownership/postimage mismatch')
        old_entry = previous['entry']
        if plugins.count(old_entry) != 1:
            raise ValueError('owned plugin entry missing or duplicated')
    # A chief overlay may only be replaced with a matching prior ownership receipt.
    for plugin in plugins:
        text = json.dumps(plugin)
        options = plugin.get('options') if isinstance(plugin, dict) else None
        if (isinstance(options, dict) and options.get('routing') == 'overlay') or 'batteryshark' in text or '/revisions/' in text:
            if plugin != old_entry:
                raise ValueError('unexpected/unowned existing overlay entry')
    if old_entry == entry:
        after = config.read_bytes()
    else:
        data['plugins'] = [entry if p == old_entry else p for p in plugins] if old_entry else [*plugins, entry]
        after = encoded(data)
    return delta(config, after, 'bridge', entry=entry, before_entry=old_entry, revision=str(revision), lock=lock)


def route_upgrade(data):
    result = copy.deepcopy(data)
    strong = [r for r in result['routes'] if r['id'] == 'gpt-strong']
    if len(strong) != 1 or strong[0]['model'] != 'openai/gpt-6.1-sol' or strong[0].get('variant') != 'high':
        raise ValueError('expected unique Sol/high gpt-strong route')
    mid = {**copy.deepcopy(strong[0]), 'id': 'gpt-mid', 'variant': 'medium',
           'categories': ['implement'], 'priority': strong[0].get('priority', 0) + 1}
    if mid['priority'] > 100:
        raise ValueError('cannot safely prioritize medium')
    existing = [r for r in result['routes'] if r['id'] == 'gpt-mid']
    if existing:
        if existing != [mid]:
            raise ValueError('unexpected existing gpt-mid; no replacement authorized')
    else:
        result['routes'].insert(result['routes'].index(strong[0]), mid)
    return result


def route_plan(config):
    config = safe(config)
    data = load(config)
    upgraded = route_upgrade(data)
    return delta(config, config.read_bytes() if data == upgraded else encoded(upgraded), 'routes')


def apply_plan(plan_path, receipt_path, *, quiet=False, rollback=False):
    if not quiet:
        raise ValueError('fresh parent release/quiet window required')
    plan = load(safe(plan_path))
    if plan['uid'] != os.getuid() or plan['kind'] not in ('bridge', 'routes'):
        raise ValueError('plan ownership/kind mismatch')
    target = safe(plan['target'])
    before, after = (base64.b64decode(plan[k], validate=True) for k in ('before', 'after'))
    if digest(before) != plan['before_sha256'] or digest(after) != plan['after_sha256']:
        raise ValueError('corrupt plan')
    # Recompute allowed delta; arbitrary edited plans must not write unrelated values.
    if plan['kind'] == 'routes':
        parsed = json.loads(before)
        upgraded = route_upgrade(parsed)
        expected = before if parsed == upgraded else encoded(upgraded)
    else:
        if target.name != 'opencode.json' or target.parent.name != '.opencode' or target.parent.parent.name != '.chief-of-staff':
            raise ValueError('chief-local target required')
        locked = lockfile()
        if plan['entry'] != {'package': str(Path(plan['revision']) / 'dist'), 'options': locked['options']}:
            raise ValueError('unreviewed plugin entry/options')
        if not rollback:
            verified(Path(plan['revision']), locked)
        a, b = json.loads(before), json.loads(after)
        allowed = copy.deepcopy(a)
        previous = plan.get('before_entry')
        plugins = a.get('plugins', [])
        if previous and (not isinstance(previous, dict) or previous.get('options') != locked['options']
                         or not re.search(r'/revisions/[0-9a-f]{40}/dist$', previous.get('package', ''))):
            raise ValueError('previous entry is not an owned bridge revision')
        if previous and plugins.count(previous) != 1:
            raise ValueError('previous owned entry not unique')
        allowed['plugins'] = ([plan['entry'] if e == previous else e for e in plugins]
                              if previous else [*plugins, plan['entry']])
        if allowed != b or b.get('plugins', []).count(plan['entry']) != 1:
            raise ValueError('bridge delta exceeds owned plugin scope')
        expected = after
    if expected != after:
        raise ValueError('delta differs from scoped upgrade')
    old, new = (after, before) if rollback else (before, after)
    if target.read_bytes() != old:
        raise ValueError('exact preimage/postimage changed; stop without writes')
    # Absent-only backup/receipt before the config change. Retained on any failure.
    create(receipt_path, encoded(plan))
    fd, name = tempfile.mkstemp(prefix='.chief-delta-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), target.stat().st_mode & 0o777)
            out.write(new)
            out.flush()
            os.fsync(out.fileno())
        safe(target)
        if target.read_bytes() != old:
            raise ValueError('preimage changed during write')
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def release_version(value):
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('stable named release required')
    return tuple(map(int, value.lstrip('v').split('.')))


def metadata(lock):
    def get(url):
        request = urllib.request.Request(url, headers={'User-Agent': 'chief-bridge-update-check'})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read(2 * 1024 * 1024))
    gh = get(f"https://api.github.com/repos/{lock['upstream']['github']}/releases/latest")
    npm = get(f"https://registry.npmjs.org/{lock['upstream']['npm']}/latest")
    tag = gh['tag_name']
    if gh.get('draft') or gh.get('prerelease') or release_version(tag) != release_version(npm['version']):
        raise ValueError('official GitHub/npm stable release metadata disagree; stop')
    return tag


def check_update(managed, lock, bun, *, source_repo=None, upstream_repo=None, release=None, builder=build):
    tag = release or metadata(lock)
    if release_version(tag) <= release_version(lock['upstream']['release']):
        return {'status': 'current', 'release': tag, 'installed_pin': lock['commit']}
    candidates = safe(Path(managed) / 'candidates')
    candidates.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='release-', dir=candidates))
    repo = stage / 'source'
    report = {'status': 'stopped', 'release': tag, 'installed_pin': lock['commit'], 'candidate': str(repo)}
    try:
        clone_source(repo, lock, source_repo)
        git(repo, 'fetch', '--no-tags', '--', upstream_repo or lock['upstream']['repository'], f'refs/tags/{tag}')
        base = git(repo, 'rev-parse', 'FETCH_HEAD^{commit}')
        patches = git(repo, 'rev-list', '--reverse', f"{lock['upstream']['base']}..{lock['commit']}").splitlines()
        git(repo, 'checkout', '-b', 'chief-candidate', base)
        for commit in patches:
            git(repo, '-c', 'user.name=Chief candidate', '-c', 'user.email=candidate@localhost', 'cherry-pick', commit)
        candidate_lock = copy.deepcopy(lock)
        candidate_lock.update(commit=git(repo, 'rev-parse', 'HEAD'), tree=git(repo, 'rev-parse', 'HEAD^{tree}'),
                              bun_lock_sha256=digest((repo / 'bun.lock').read_bytes()))
        candidate_lock['upstream'].update(base=base, release=tag.lstrip('v'), tag=tag)
        checks = builder(repo, candidate_lock, bun)
        report.update(status='candidate-tested-not-promoted', checks=checks, candidate_lock=candidate_lock)
    except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
        report['error'] = str(exc)
    create(stage / 'report.json', encoded(report))
    return report
