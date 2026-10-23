import copy
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chief_bridge as kit
from runway.policy import decide, timestamp
from test_routing import source, NOW


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = self.root / '.chief-of-staff/.opencode/opencode.json'
        self.config.parent.mkdir(parents=True)
        self.original = b'{"plugins":["stock"], "permissions":{"shell":"ask"}, "default_agent":"chief-of-staff"}\n'
        self.config.write_bytes(self.original)
        self.lock = kit.lockfile()
        self.revision = self.root / 'managed/revisions' / self.lock['commit']

    def plan(self, previous=None):
        with patch.object(kit, 'verified', return_value={'package': str(self.revision / 'dist')}):
            return kit.bridge_plan(self.config, self.revision, self.lock, previous)

    def save(self, name, value):
        path = self.root / name
        kit.create(path, kit.encoded(value))
        return path

    def apply(self, plan, receipt, **kwargs):
        with patch.object(kit, 'verified'):
            kit.apply_plan(plan, self.root / receipt, **kwargs)

    def test_scope_idempotence_and_exact_rollback(self):
        plan = self.save('plan', self.plan())
        self.assertEqual(self.config.read_bytes(), self.original)
        self.apply(plan, 'receipt', quiet=True)
        data = kit.load(self.config)
        self.assertEqual(data['plugins'][0], 'stock')
        self.assertEqual(data['permissions'], {'shell': 'ask'})
        self.assertEqual(data['plugins'][1]['package'], str(self.revision / 'dist'))
        again = self.plan(self.root / 'receipt')
        self.assertEqual(again['before'], again['after'])
        self.apply(self.root / 'receipt', 'rollback-receipt', quiet=True, rollback=True)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_quiet_window_preimage_postimage_and_absent_receipt_guards(self):
        plan = self.save('plan', self.plan())
        with self.assertRaisesRegex(ValueError, 'quiet window'):
            self.apply(plan, 'receipt')
        self.config.write_bytes(self.original + b' ')
        with self.assertRaisesRegex(ValueError, 'preimage'):
            self.apply(plan, 'receipt', quiet=True)
        self.config.write_bytes(self.original)
        self.apply(plan, 'receipt', quiet=True)
        post = self.config.read_bytes()
        self.config.write_bytes(post + b' ')
        with self.assertRaisesRegex(ValueError, 'postimage'):
            self.apply(self.root / 'receipt', 'undo', quiet=True, rollback=True)
        self.assertEqual(self.config.read_bytes(), post + b' ')

    def test_symlinks_unowned_entries_and_nonchief_target_refused(self):
        data = kit.load(self.config)
        data['plugins'].append({'package': '/other/dist', 'options': self.lock['options']})
        self.config.write_bytes(kit.encoded(data))
        with self.assertRaisesRegex(ValueError, 'unowned'):
            self.plan()
        self.config.unlink()
        other = self.root / 'other'
        other.write_bytes(self.original)
        self.config.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.plan()
        with self.assertRaisesRegex(ValueError, 'chief-local'):
            kit.bridge_plan(other, self.revision, self.lock)
        with patch('chief_bridge.os.getuid', return_value=os.getuid() + 1):
            with self.assertRaisesRegex(ValueError, 'ownership'):
                kit.safe(other)

    def test_tampered_delta_and_overwrite_refused(self):
        value = self.plan()
        after = json.loads(__import__('base64').b64decode(value['after']))
        after['plugins'][0] = 'remove-stock'
        value['after'] = __import__('base64').b64encode(kit.encoded(after)).decode()
        value['after_sha256'] = kit.digest(kit.encoded(after))
        with self.assertRaisesRegex(ValueError, 'scope'):
            self.apply(self.save('bad', value), 'receipt', quiet=True)
        with self.assertRaises(FileExistsError):
            self.save('bad', value)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_frozen_build_commands_and_sdk_guard(self):
        repo = self.root / 'build'
        (repo / 'node_modules/@anthropic-ai/claude-agent-sdk').mkdir(parents=True)
        (repo / 'bun.lock').write_text('frozen')
        package = repo / 'node_modules/@anthropic-ai/claude-agent-sdk/package.json'
        package.write_text('{"version":"0.3.224"}')
        (repo / 'dist').mkdir()
        (repo / 'dist/index.js').write_text('export default {}')
        with patch.object(kit, 'run', return_value='pass') as run:
            kit.build(repo, self.lock, '/cached/bun')
        self.assertEqual(run.call_args_list[0].args[0], ['/cached/bun', 'install', '--frozen-lockfile', '--ignore-scripts'])
        self.assertEqual(run.call_args_list[1].args[0], ['/cached/bun', 'run', 'build'])
        self.assertEqual(run.call_args_list[2].args[0], ['/cached/bun', 'test/run.ts'])
        package.write_text('{"version":"0.3.225"}')
        with patch.object(kit, 'run', return_value='pass'), self.assertRaisesRegex(ValueError, 'SDK'):
            kit.build(repo, self.lock, '/cached/bun')

    def test_official_named_metadata_agreement_and_conflict(self):
        # Assert the production package identity, not just matching mock versions.
        self.assertEqual(kit.lockfile()['upstream']['npm'], '@openchamber/opencode-claude')
        urls = []
        def response(req, timeout):
            urls.append(req.full_url)
            self.assertEqual(timeout, 15)
            data = {'tag_name': 'v1.6.0'} if 'api.github.com' in req.full_url else {'version': '1.6.0'}
            return io.BytesIO(json.dumps(data).encode())
        with patch('chief_bridge.urllib.request.urlopen', side_effect=response):
            self.assertEqual(kit.metadata(self.lock), 'v1.6.0')
        self.assertEqual(urls, ['https://api.github.com/repos/openchamber/opencode-claude/releases/latest',
                                'https://registry.npmjs.org/@openchamber/opencode-claude/latest'])
        with patch('chief_bridge.urllib.request.urlopen', side_effect=[
                io.BytesIO(b'{"tag_name":"v1.6.0"}'), io.BytesIO(b'{"version":"1.5.0"}')]):
            with self.assertRaisesRegex(ValueError, 'disagree'):
                kit.metadata(self.lock)


class GitMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'fork'
        self.repo.mkdir()
        kit.run(['git', 'init', self.repo])
        kit.git(self.repo, 'config', 'user.name', 'Fixture')
        kit.git(self.repo, 'config', 'user.email', 'fixture@localhost')
        (self.repo / 'bun.lock').write_text('frozen fixture')
        (self.repo / 'role.txt').write_text('base\n')
        self.commit('base')
        self.base = kit.git(self.repo, 'rev-parse', 'HEAD')
        (self.repo / 'role.txt').write_text('chief\n')
        self.commit('reviewed patch')
        self.lock = kit.lockfile()
        self.lock.update(commit=kit.git(self.repo, 'rev-parse', 'HEAD'), tree=kit.git(self.repo, 'rev-parse', 'HEAD^{tree}'),
                         bun_lock_sha256=kit.digest((self.repo / 'bun.lock').read_bytes()))
        self.lock['upstream']['base'] = self.base
        self.installed = self.root / 'installed.lock'
        self.installed.write_bytes(kit.encoded(self.lock))

    def commit(self, name):
        kit.git(self.repo, 'add', '.')
        kit.git(self.repo, 'commit', '-m', name)

    def release(self, conflict=False):
        kit.git(self.repo, 'checkout', '-b', 'upstream-fixture', self.base)
        (self.repo / ('role.txt' if conflict else 'new.txt')).write_text('upstream\n')
        self.commit('next release')
        kit.git(self.repo, 'tag', 'v1.6.0')
        kit.git(self.repo, 'checkout', '--detach', self.lock['commit'])

    def check(self, **kwargs):
        return kit.check_update(self.root / 'managed', self.lock, 'cached-bun', source_repo=self.repo,
                                upstream_repo=self.repo, **kwargs)

    def test_current_does_not_clone_or_build(self):
        with patch.object(kit, 'clone_source', side_effect=AssertionError('unexpected clone')):
            self.assertEqual(self.check(release='v1.5.0')['status'], 'current')

    def test_new_release_replay_tested_pin_unchanged(self):
        self.release()
        before = self.installed.read_bytes()
        def builder(repo, lock, bun):
            self.assertEqual((repo / 'role.txt').read_text(), 'chief\n')
            self.assertEqual((repo / 'new.txt').read_text(), 'upstream\n')
            return {'offline': 'pass'}
        result = self.check(release='v1.6.0', builder=builder)
        self.assertEqual(result['status'], 'candidate-tested-not-promoted', result)
        self.assertEqual(before, self.installed.read_bytes())
        self.assertEqual(kit.git(self.repo, 'rev-parse', 'HEAD'), self.lock['commit'])

    def test_conflict_and_test_failure_stop_without_pin_writes(self):
        self.release(conflict=True)
        before = self.installed.read_bytes()
        result = self.check(release='v1.6.0', builder=lambda *a: self.fail('conflict must not build'))
        self.assertEqual(result['status'], 'stopped')
        self.assertIn('failed', result['error'])
        self.assertEqual(before, self.installed.read_bytes())

    def test_build_failure_stops(self):
        self.release()
        def fail(*args):
            raise ValueError('offline tests failed')
        result = self.check(release='v1.6.0', builder=fail)
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(self.installed.read_bytes(), kit.encoded(self.lock))

    def test_local_source_exact_clean_integrity_and_unpublished_stop(self):
        kit.clone_source(self.root / 'clone', self.lock, self.repo)
        (self.repo / 'untracked.txt').write_text('not owned build input')
        with self.assertRaisesRegex(ValueError, 'clean'):
            kit.clone_source(self.root / 'dirty-clone', self.lock, self.repo)
        missing = copy.deepcopy(self.lock)
        missing['repository'] = str(self.root / 'clone')
        missing['commit'] = 'a' * 40
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            kit.clone_source(self.root / 'unpublished', missing)

    def test_prepare_reuse_and_integrity_guard(self):
        def built(repo, lock, bun):
            (repo / 'dist').mkdir()
            (repo / 'dist/index.js').write_text('export default {}')
            sdk = repo / 'node_modules/@anthropic-ai/claude-agent-sdk'
            sdk.mkdir(parents=True)
            (sdk / 'package.json').write_text('{"version":"0.3.224"}')
            # Real package sources ignore generated output; fixtures do likewise.
            (repo / '.git/info/exclude').write_text('dist/\nnode_modules/\n.chief-ready.json\n')
            return {'sdk': '0.3.224', 'dist_sha256': kit.dist_hash(repo)}
        with patch.object(kit, 'build', side_effect=built) as build:
            first = kit.prepare(self.root / 'managed', self.lock, 'cached-bun', self.repo)
            again = kit.prepare(self.root / 'managed', self.lock, 'cached-bun', self.repo)
            self.assertEqual(first, again)
            self.assertEqual(build.call_count, 1)
        (Path(first['package']) / 'index.js').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'changed'):
            kit.prepare(self.root / 'managed', self.lock, 'cached-bun', self.repo)


class RouteTests(unittest.TestCase):
    def test_example_medium_policy_and_shared_caps(self):
        example = kit.load(kit.ROOT / 'routing/routes.example.json')
        config = kit.route_upgrade(example)
        self.assertEqual(config, kit.route_upgrade(config))
        strong = next(r for r in config['routes'] if r['id'] == 'gpt-strong')
        mid = next(r for r in config['routes'] if r['id'] == 'gpt-mid')
        for k in strong:
            if k not in ('id', 'variant', 'categories', 'priority'):
                self.assertEqual(strong[k], mid[k])
        config['routes'] = [mid, strong]
        catalog = {'directory': '/repo', 'observed_at': timestamp(NOW), 'models': [{
            'providerID': 'openai', 'id': 'gpt-6.1-sol', 'enabled': True, 'status': 'active',
            'capabilities': {'tools': True, 'input': ['text']}, 'limit': {'context': 128000},
            'variants': [{'id': 'high'}, {'id': 'medium'}]}]}
        snapshot = {'schema_version': 2, 'passive': True, 'sources': [source('codex')]}
        task = {'scope': '/scope', 'directory': '/repo', 'job': 'job', 'category': 'implement', 'size': 'small'}
        self.assertEqual(decide(config, snapshot, catalog, task, [], None, NOW)['selected']['route'], 'gpt-mid')
        task['category'] = 'hard'
        self.assertEqual(decide(config, snapshot, catalog, task, [], None, NOW)['selected']['route'], 'gpt-strong')
        attempts = [{'pool': strong['pool'], 'state': 'running', 'reservation': []}] * strong['max_parallel']
        self.assertIsNone(decide(config, snapshot, catalog, task, attempts, None, NOW)['selected'])
        task['category'] = 'implement'
        self.assertIsNone(decide(config, snapshot, catalog, task, attempts, None, NOW)['selected'])
        catalog['models'][0]['variants'] = [{'id': 'high'}]
        self.assertEqual(decide(config, snapshot, catalog, task, [], None, NOW)['selected']['route'], 'gpt-strong')

    def test_operator_values_unknown_settings_and_guarded_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = str(Path(tmp).resolve())
            path = Path(tmp) / 'routes.json'
            data = kit.load(kit.ROOT / 'routing/routes.example.json')
            data['routes'] = [r for r in data['routes'] if r['id'] != 'gpt-mid']
            strong = next(r for r in data['routes'] if r['id'] == 'gpt-strong')
            strong.update(account='operator', source='actual-source', max_parallel=10, reserve_percent=2, custom='keep')
            data['operator_setting'] = {'keep': True}
            original = kit.encoded(data)
            path.write_bytes(original)
            plan = kit.route_plan(path)
            planpath = Path(tmp) / 'plan'
            kit.create(planpath, kit.encoded(plan))
            kit.apply_plan(planpath, Path(tmp) / 'receipt', quiet=True)
            after = kit.load(path)
            self.assertEqual([r for r in after['routes'] if r['id'] != 'gpt-mid'], data['routes'])
            self.assertEqual(after['operator_setting'], data['operator_setting'])
            mid = next(r for r in after['routes'] if r['id'] == 'gpt-mid')
            self.assertEqual((mid['max_parallel'], mid['reserve_percent'], mid['custom']), (10, 2, 'keep'))
            kit.apply_plan(Path(tmp) / 'receipt', Path(tmp) / 'undo', quiet=True, rollback=True)
            self.assertEqual(path.read_bytes(), original)


class EntrypointTests(unittest.TestCase):
    def test_dedicated_dry_modes_no_outward_effects(self):
        for action in ('prepare', 'check', 'plan', 'activate', 'rollback', 'routes-plan'):
            result = subprocess.run(['bash', str(kit.ROOT / 'install.sh'), '--chief-bridge', action, '--dry-run'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('no fetch/build/config writes', result.stdout)

    def test_normal_detection_scoped_and_before_mutation(self):
        text = (kit.ROOT / 'install.sh').read_text()
        self.assertIn('if [[ $mode == install && " ${hosts[*]} " == *" opencode "* ]]', text)
        self.assertLess(text.index('"$SRC/scripts/chief-bridge.py" check\n'), text.index('targets()'))
        self.assertLess(text.index('if [[ $profile != technical ]]'), text.index('# Finite technical/OpenCode'))

    def test_executed_entrypoint_detection_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'bin').mkdir()
            shim = root / 'bin/python3'
            shim.write_text('#!/bin/bash\nif [[ "$1" == */chief-bridge.py ]]; then echo check >> "$HOME/checks"; exit 31; fi\nexit 0\n')
            shim.chmod(0o700)
            env = {**os.environ, 'HOME': str(root), 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH']}
            for args in (['opencode'], [], ['--chief-bridge-check']):
                result = subprocess.run(['bash', str(kit.ROOT / 'install.sh'), *args], env=env, capture_output=True)
                self.assertEqual(result.returncode, 31)
            self.assertEqual((root / 'checks').read_text().splitlines(), ['check'] * 3)
            for args in (['--dry-run', 'opencode'], ['--print', 'opencode'], ['--uninstall', 'opencode'],
                         ['--profile', 'example', 'opencode']):
                subprocess.run(['bash', str(kit.ROOT / 'install.sh'), *args], env=env, capture_output=True)
            self.assertEqual((root / 'checks').read_text().splitlines(), ['check'] * 3)
