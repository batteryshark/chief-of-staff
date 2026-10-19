"""Courtesy-only ownership regressions. All writes are in a private HOME."""
import os
import json
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_upstream_courtesy as fixtures
from courtesy import MARKER, skill, target, preflight
from courtesy_owned import OwnedSkills, metadata, digest, LEDGER, source_pin


class CourtesySafetyTests(fixtures.CourtesyTests):
    # Do not inherit/rerun the broader suite in this focused lane.
    def test_modified_default_refused_before_legacy_install_and_uninstall(self):
        self.install('opencode')
        p = target(self.home, 'opencode')
        p.write_text(p.read_text() + 'User notes\n')
        before = self.snapshot()
        self.install('opencode', ok=False)
        self.assertEqual(before, self.snapshot())
        self.install('--uninstall', 'opencode', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_marker_only_and_exact_unrecorded_are_not_owned(self):
        p = target(self.home, 'opencode')
        p.parent.mkdir(parents=True)
        for text in (MARKER + '\nunrelated prose', skill()):
            p.write_text(text)
            before = self.snapshot()
            self.install(ok=False)
            self.assertEqual(before, self.snapshot())

    def test_last_unsafe_parent_prevents_first_host_and_legacy_writes(self):
        p = target(self.home, 'codex').parent
        p.mkdir(parents=True)
        p.chmod(0o777)
        before = self.snapshot()
        self.install(ok=False)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(target(self.home, 'opencode').exists())

    def test_existing_canonical_hardlink_is_refused(self):
        p = target(self.home, 'opencode')
        p.parent.mkdir(parents=True)
        p.write_text(skill())
        os.link(p, self.home / 'user-copy')
        with self.assertRaises(ValueError):
            preflight(self.home, ['opencode'])

    def test_modified_shared_default_not_reused(self):
        self.install()
        p = target(self.home, 'codex')
        p.write_text(p.read_text() + 'private addition')
        before = self.snapshot()
        self.install('--lead-config', self.config(['research']), ok=False)
        self.assertEqual(before, self.snapshot())

    def test_modified_standalone_and_owner_collision(self):
        args = ('--lead-config', self.config(['research']))
        self.install(*args)
        p = target(self.home, 'codex')
        p.write_text(p.read_text() + 'notes')
        before = self.snapshot()
        self.install(*args, ok=False)
        self.install('--uninstall', *args, ok=False)
        self.assertEqual(before, self.snapshot())

    def owned(self, **kwargs):
        return OwnedSkills(self.home, {target(self.home, h): skill()
                                      for h in ('opencode', 'claude', 'codex')}, **kwargs)

    def test_other_standalone_and_global_owner_collisions(self):
        cfg = Path(self.config(['research']))
        self.install('--lead-config', str(cfg))
        data = json.loads(cfg.read_text())
        data['agent'] = 'different-owner'
        cfg.write_text(json.dumps(data))
        before = self.snapshot()
        self.install('--lead-config', str(cfg), ok=False)
        self.install(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_uid_type_modes_and_system_ancestor_metadata(self):
        safe = dict(st_mode=stat.S_IFDIR | 0o755, st_uid=os.getuid(), st_nlink=3)
        metadata(SimpleNamespace(**safe), directory=True)
        metadata(SimpleNamespace(**{**safe, 'st_uid': 0}), directory=True, system=True)
        for change in ({'st_uid': os.getuid()+1}, {'st_mode': stat.S_IFDIR | 0o775},
                       {'st_mode': stat.S_IFDIR | 0o757}, {'st_mode': stat.S_IFLNK | 0o755}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                metadata(SimpleNamespace(**{**safe, **change}), directory=True)
        with self.assertRaises(ValueError):
            metadata(SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.getuid(), st_nlink=2))

    def test_trusted_home_and_existing_owned_dirs_modes(self):
        self.home.chmod(0o775)
        with self.assertRaises(ValueError): self.owned()
        self.home.chmod(0o750)
        self.owned().install()
        for h in ('opencode', 'claude', 'codex'):
            p = target(self.home, h)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(p.parent.stat().st_mode), 0o700)
        self.owned().install()  # trusted exact no-op, no receipt churn

    def test_owned_hardlink_and_last_host_uninstall_preflight(self):
        self.install()
        p = target(self.home, 'codex')
        os.link(p, self.home / 'copy')
        before = self.snapshot()
        self.install('--uninstall', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_private_ledger_unknown_or_edited_receipt_refused(self):
        owned = self.owned()
        owned.install()
        p = target(self.home, 'codex')
        r = owned.record_path(p)
        data = json.loads(r.read_text())
        data['sha256'] = '0'*64
        r.write_text(json.dumps(data))
        before = self.snapshot()
        self.install(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_malformed_last_receipt_blocks_all_default_and_legacy_mutation(self):
        self.install()
        r = self.owned().record_path(target(self.home, 'codex'))
        data = json.loads(r.read_bytes())
        data['dirs'] = 'invalid'
        r.write_text(json.dumps(data))
        before = self.snapshot()
        self.install(ok=False)
        self.assertEqual(before, self.snapshot())
        self.install('--uninstall', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_malformed_last_receipt_blocks_standalone_legacy_mutation(self):
        args = ('--lead-config', self.config(['research']))
        self.install(*args)
        r = OwnedSkills(self.home, {}).record_path(target(self.home, 'codex'))
        data = json.loads(r.read_bytes())
        del data['run']
        r.write_text(json.dumps(data))
        before = self.snapshot()
        self.install(*args, ok=False)
        self.assertEqual(before, self.snapshot())
        self.install('--uninstall', *args, ok=False)
        self.assertEqual(before, self.snapshot())

    def test_malformed_scoped_receipt_blocks_inventory_and_other_outputs(self):
        args = ('--profile', 'example')
        self.install(*args)
        p = self.home / '.chiefs/example/.opencode/skills/upstream-courtesy/SKILL.md'
        r = OwnedSkills(self.home, {}).record_path(p)
        data = json.loads(r.read_bytes())
        data['dirs'].append({'path': '.chiefs/unrelated', 'file': data['file']})
        r.write_text(json.dumps(data))
        before = self.snapshot()
        self.install(*args, ok=False)
        self.assertEqual(before, self.snapshot())
        self.install('--uninstall', *args, ok=False)
        self.assertEqual(before, self.snapshot())

    def test_exact_6fc58e9_all22_output_parity(self):
        from hygiene_fixtures import outputs, pinned_print
        oldroot = self.root / '6fc58e9'
        old = outputs(pinned_print('6fc58e9', oldroot, self.env), oldroot, self.home)
        new = outputs(self.install('--print'), fixtures.SRC, self.home)
        self.assertEqual(len(new), 22)
        self.assertEqual(new, old)
        for path, text in new.items():
            if '/upstream-courtesy/SKILL.md' in path:
                self.assertEqual(text, skill() + '\n')
            else:
                self.assertNotIn('upstream-courtesy', text)

    def test_helper_partial_failure_rolls_back_exact_creations_only(self):
        owned = self.owned()
        original = owned.exclusive
        def fail(p, data):
            if p == target(self.home, 'claude'):
                raise OSError('injected second-leaf create failure')
            return original(p, data)
        with patch.object(owned, 'exclusive', side_effect=fail), self.assertRaises(OSError):
            owned.install()
        self.assertFalse(any(target(self.home, h).exists() for h in ('opencode', 'claude', 'codex')))
        self.assertFalse(any(p.is_file() for p in self.home.rglob('*')))

    def test_partial_failure_retains_later_edit_and_user_file(self):
        owned = self.owned()
        original = owned.exclusive
        first = target(self.home, 'opencode')
        def fail(p, data):
            if p == target(self.home, 'claude'):
                first.write_text('later user edit')
                (first.parent / 'notes').write_text('user')
                raise OSError('injected failure')
            return original(p, data)
        with patch.object(owned, 'exclusive', side_effect=fail), self.assertRaises(OSError):
            owned.install()
        self.assertEqual(first.read_text(), 'later user edit')
        self.assertEqual((first.parent / 'notes').read_text(), 'user')
        self.assertTrue(owned.record_path(first).exists())

    def test_rollback_retains_replaced_same_bytes_and_edits_nonempty_dirs(self):
        owned = self.owned()
        run = owned.install()
        first, second, third = [target(self.home, h) for h in ('opencode', 'claude', 'codex')]
        temp = first.with_name('replacement')
        temp.write_text(skill())
        temp.chmod(0o600)
        temp.replace(first)
        second.write_text(second.read_text() + 'user notes')
        user = third.parent / 'notes'
        user.write_text('retain')
        self.owned(rollback=True).rollback(run)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertFalse(third.exists())
        self.assertEqual(user.read_text(), 'retain')

    def test_helper_cli_only_three_leaves_and_metadata_no_legacy_mutation(self):
        self.install()
        # Broad install provides legacy fixtures; exact-owned helper must be a no-op.
        before = self.snapshot()
        cmd = ['python3', str(fixtures.SRC / 'scripts/install-courtesy.py'), 'install',
               '--home', str(self.home), '--source-pin', source_pin(),
               '--skill-sha256', digest(skill().encode())]
        p = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(before, self.snapshot())

    def test_strict_helper_fresh_diff_only_three_skills_and_private_receipts(self):
        for name in ('old-agent.md', '.kit-install.json', 'settings.json', 'native-output'):
            (self.home / name).write_text('untouched fixture')
        before = self.snapshot()
        owned = self.owned()
        run = owned.install()
        after = self.snapshot()
        for p, h in before.items(): self.assertEqual(after[p], h)
        expected = {str(target(self.home, h).relative_to(self.home)) for h in ('opencode', 'claude', 'codex')}
        expected |= {str(owned.record_path(p).relative_to(self.home)) for p in owned.outputs}
        self.assertEqual(set(after) - set(before), expected)
        self.owned(rollback=True).rollback(run)
        self.assertEqual(before, self.snapshot())

    def test_exact_7f780dd_old19_only_approved_canonical_skill_delta(self):
        from hygiene_fixtures import outputs, pinned_print
        oldroot = self.root / '7f780dd'
        old = outputs(pinned_print('7f780dd', oldroot, self.env), oldroot, self.home)
        new = outputs(self.install('--print'), fixtures.SRC, self.home)
        for h in ('opencode', 'claude', 'codex'):
            p = str(target(Path('<HOME>'), h))
            oldtext = old.pop(p)
            self.assertEqual(digest(oldtext[:-1].encode()), '145dff55d7417117b02aa43abc693855a17901bc7100b8024ae131ca02dae837')
            from courtesy_fixtures import approved_n1
            self.assertEqual(approved_n1(oldtext), skill() + '\n')
            self.assertEqual(new.pop(p), skill() + '\n')
        self.assertEqual(len(new), 19)
        self.assertEqual(new, old)
        self.assertFalse(any('upstream-courtesy' in text for text in new.values()))

    def test_n1_finite_approval_and_policy_cases(self):
        text = skill()
        for phrase in ('finite enumerated', 'Changed/unlisted actions need a fresh yes',
                       'Unknown/unavailable policy stays unknown', 'absence of a published AI policy is not refusal',
                       'even with principal approval', 'One issue per distinct bug', 'short plain professional prose'):
            self.assertIn(phrase, text)
        self.assertEqual((fixtures.SRC / 'skills/upstream-courtesy/SKILL.md').read_text(), text)


# Keep only the six focused regressions, not CourtesyTests' ten inherited cases.
for _name in list(fixtures.CourtesyTests.__dict__):
    if _name.startswith('test_'):
        setattr(CourtesySafetyTests, _name, None)
