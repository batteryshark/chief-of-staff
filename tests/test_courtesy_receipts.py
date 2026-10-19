"""R3: real private filesystem receipts, no live HOME or privileged operations."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.environ.get('COURTESY_TEST_SOURCE', str(Path(__file__).resolve().parents[1] / 'scripts')))
from courtesy import skill, target, MARKER
from courtesy_owned import OwnedSkills, digest


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.home.mkdir(mode=0o700)
        self.outputs = {target(self.home, h): skill() for h in ('opencode', 'claude', 'codex')}
        self.owned = OwnedSkills(self.home, self.outputs)
        self.run = self.owned.install()
        self.last = target(self.home, 'codex')
        self.receipt = self.owned.record_path(self.last)

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.lstat().st_ino, stat.S_IMODE(p.lstat().st_mode),
                                               p.read_bytes() if p.is_file() else None)
                for p in [self.home, *self.home.rglob('*')]}

    def edit(self, change):
        data = json.loads(self.receipt.read_bytes())
        change(data)
        self.receipt.write_text(json.dumps(data))

    def rollback(self):
        OwnedSkills(self.home, self.outputs, rollback=True).rollback(self.run)

    def refused_unchanged(self, action):
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError)):
            action()
        self.assertEqual(before, self.snapshot())

    def test_r3_invalid_dirs_rollback_retains_all(self):
        self.edit(lambda d: d.update(dirs='invalid'))
        self.refused_unchanged(self.rollback)

    def test_r3_noncanonical_leaf_and_receipt_hash_retained(self):
        self.last.write_text('user notes, not skill')
        self.edit(lambda d: d.update(sha256=digest(self.last.read_bytes())))
        self.refused_unchanged(self.rollback)

    def test_r3_missing_run_malformed_dirs_reinstall_refused(self):
        self.edit(lambda d: (d.pop('run'), d.update(dirs='invalid')))
        self.refused_unchanged(lambda: OwnedSkills(self.home, self.outputs).install())

    def test_schema_negative_matrix_before_any_mutation(self):
        original = self.receipt.read_bytes()
        base = json.loads(original)
        changes = [None, [], True, 1, 'receipt']
        changes += [{**base, **v} for v in (
            {'version': 2}, {'version': True}, {'version': 1.0}, {'owner': 'other'},
            {'owner': None}, {'path': '/absolute'}, {'path': '../escape'},
            {'path': '.codex//skills/upstream-courtesy/SKILL.md'},
            {'run': None}, {'run': True}, {'run': ''}, {'run': 'x'*32},
            {'run': 'a'*10000}, {'run': self.run.upper()},
            {'sha256': 'A'*64}, {'sha256': '0'*63}, {'sha256': None},
            {'extra': 1}, {'file': None}, {'file': []}, {'dirs': None},
            {'dirs': {}}, {'dirs': False}, {'dirs': [None]}, {'dirs': [{}]},
        )]
        changes += [{k: v for k, v in base.items() if k != missing} for missing in base]
        for key in ('dev', 'ino', 'uid', 'mode'):
            for bad in (None, True, 1.5, -1, 2**80, '600'):
                changes.append({**base, 'file': {**base['file'], key: bad}})
        changes += [{**base, 'file': {**base['file'], 'extra': 1}},
                    {**base, 'file': {k: v for k, v in base['file'].items() if k != 'ino'}}]
        entry = base['dirs'][-1]
        for path in ('../escape', '/absolute', '.', '.codex//skills', '.codex/skills/../skills',
                     '.codex/skills/unrelated', '.config/chief-of-staff/other'):
            changes.append({**base, 'dirs': [{**entry, 'path': path}]})
        changes += [{**base, 'dirs': [entry, entry]}, {**base, 'dirs': [entry]*1000},
                    {**base, 'dirs': [{**entry, 'extra': 1}]},
                    {**base, 'dirs': [{'path': entry['path']}]},
                    {**base, 'dirs': [{**entry, 'file': {**entry['file'], 'ino': True}}]},
                    {**base, 'dirs': [{**entry, 'file': {**entry['file'], 'mode': 0o755}}]}]
        raw_cases = [b'{', b'{"version":1,"version":1}', original.replace(b'"dev":', b'"dev":0,"dev":', 1),
                     original + b' '*65536, b'['*2000 + b']'*2000]
        raw_cases += [json.dumps(d).encode() for d in changes]
        for raw in raw_cases:
            with self.subTest(raw=raw[:150]):
                self.receipt.write_bytes(raw)
                self.refused_unchanged(self.rollback)
                self.refused_unchanged(lambda: OwnedSkills(self.home, self.outputs).install())
                self.refused_unchanged(lambda: OwnedSkills(self.home, self.outputs).uninstall())
        self.receipt.write_bytes(original)

    def test_receipt_changes_after_validation_before_leaf_unlink(self):
        for replacement in ('bytes', 'inode'):
            with self.subTest(replacement=replacement):
                owned = OwnedSkills(self.home, self.outputs, rollback=True)
                original = owned.remove
                saved = self.receipt.read_bytes()
                def change(p, rec):
                    if p == self.last:
                        if replacement == 'bytes':
                            self.receipt.write_bytes(saved + b' ')
                        else:
                            temp = self.receipt.with_suffix('.new')
                            temp.write_bytes(saved)
                            temp.chmod(0o600)
                            temp.replace(self.receipt)
                    return original(p, rec)
                with patch.object(owned, 'remove', side_effect=change):
                    owned.rollback(self.run)
                self.assertTrue(self.last.exists())
                self.assertTrue(self.receipt.exists())

    def test_partial_cleanup_retains_unexpected_receipt(self):
        # Start a distinct owned fixture; leave setUp's installation intact.
        home = self.home / 'partial'
        home.mkdir(mode=0o700)
        outputs = {target(home, h): skill() for h in ('opencode', 'claude')}
        owned = OwnedSkills(home, outputs)
        first, second = outputs
        r = owned.record_path(first)
        exclusive = owned.exclusive
        def fail(p, data):
            if p == second:
                r.write_bytes(r.read_bytes() + b' ')
                raise OSError('fixture second leaf failure')
            return exclusive(p, data)
        with patch.object(owned, 'exclusive', side_effect=fail), self.assertRaises(OSError):
            owned.install()
        self.assertEqual(first.read_text(), skill())
        self.assertTrue(r.exists())

    def test_leaf_without_committed_receipt_is_unknown(self):
        home = self.home / 'crash'
        home.mkdir(mode=0o700)
        p = target(home, 'codex')
        owned = OwnedSkills(home, {p: skill()})
        original = owned.exclusive
        def fail(path, data):
            if path == owned.record_path(p):
                raise OSError('fixture before receipt commit')
            return original(path, data)
        with patch.object(owned, 'exclusive', side_effect=fail), self.assertRaises(OSError):
            owned.install()
        self.assertEqual(p.read_text(), skill())
        self.assertFalse(owned.record_path(p).exists())
        with self.assertRaises(ValueError):
            OwnedSkills(home, {p: skill()})

    def test_selected_owner_and_shared_default_not_deleted(self):
        standalone = {p: t.replace(MARKER, '<!-- standalone fixture -->') for p, t in self.outputs.items()}
        shared = OwnedSkills(self.home, standalone, owner='standalone:fixture', share_default=True)
        before = self.snapshot()
        shared.install()
        shared.uninstall()
        shared.rollback(self.run)
        self.assertEqual(before, self.snapshot())
        self.refused_unchanged(lambda: OwnedSkills(self.home, self.outputs, owner='scoped:fixture', rollback=True).rollback(self.run))

    def test_rollback_retains_hardlink_same_inode_edit_and_nonempty_dirs(self):
        first, second, third = self.outputs
        os.link(first, self.home / 'hardlink')
        second.write_text('user edit')
        note = third.parent / 'notes'
        note.write_text('keep')
        self.rollback()
        self.assertTrue(first.exists())
        self.assertEqual(second.read_text(), 'user edit')
        self.assertFalse(third.exists())
        self.assertEqual(note.read_text(), 'keep')

    def test_valid_multi_host_ancestor_union_and_noop(self):
        # v1 directory metadata can span the trusted selected output ancestor union.
        records = [json.loads(self.owned.record_path(p).read_bytes()) for p in self.outputs]
        union = [d for rec in records for d in rec['dirs']]
        self.edit(lambda d: d.update(dirs=union))
        before = self.snapshot()
        OwnedSkills(self.home, self.outputs).install()
        self.assertEqual(before, self.snapshot())
        self.rollback()
        self.assertFalse(any(p.exists() for p in self.outputs))

    def test_scoped_and_standalone_canonical_hashes_cannot_be_overridden(self):
        for owner in ('standalone:fixture', 'scoped:fixture'):
            with self.subTest(owner=owner):
                home = self.home / owner.replace(':', '-')
                home.mkdir(mode=0o700)
                p = home / ('scope/.opencode/skills/upstream-courtesy/SKILL.md' if owner.startswith('scoped:')
                            else '.codex/skills/upstream-courtesy/SKILL.md')
                text = skill().replace(MARKER, '<!-- ' + owner + ' -->')
                outputs = {p: text}
                owned = OwnedSkills(home, outputs, owner=owner)
                run = owned.install()
                before = self.snapshot()
                noop = OwnedSkills(home, outputs, owner=owner)
                self.assertNotEqual(noop.install(), run)  # no new receipt/run ownership
                noop.rollback(noop.run)
                self.assertEqual(before, self.snapshot())
                p.write_text('user content')
                r = owned.record_path(p)
                rec = json.loads(r.read_bytes())
                rec['sha256'] = digest(p.read_bytes())
                r.write_text(json.dumps(rec))
                self.refused_unchanged(lambda: OwnedSkills(home, outputs, owner=owner, rollback=True).rollback(run))

    def test_uninstall_receipt_change_retains_leaf_and_receipt(self):
        owned = OwnedSkills(self.home, self.outputs)
        original = owned.remove
        first = next(iter(self.outputs))
        r = owned.record_path(first)
        def change(p, rec):
            if p == first:
                r.write_bytes(r.read_bytes() + b' ')
            return original(p, rec)
        with patch.object(owned, 'remove', side_effect=change), self.assertRaises(ValueError):
            owned.uninstall()
        self.assertTrue(all(p.exists() for p in self.outputs))
        self.assertTrue(r.exists())

    def test_partial_receipt_commit_failure_retains_unknown_pair(self):
        home = self.home / 'partial-receipt'
        home.mkdir(mode=0o700)
        p = target(home, 'codex')
        owned = OwnedSkills(home, {p: skill()})
        exclusive = owned.exclusive
        def fail(path, data):
            if path == owned.record_path(p):
                exclusive(path, b'unknown partial receipt')
                raise OSError('fixture receipt write failure')
            return exclusive(path, data)
        with patch.object(owned, 'exclusive', side_effect=fail), self.assertRaises(OSError):
            owned.install()
        self.assertEqual(p.read_text(), skill())
        self.assertEqual(owned.record_path(p).read_bytes(), b'unknown partial receipt')


if __name__ == '__main__':
    unittest.main()
