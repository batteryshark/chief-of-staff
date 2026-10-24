"""Offline API-only plugin deployment; never touches installed runtime."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runway import promo_plugin_install as pi

SOURCE = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'runway').mkdir()
        text = (SOURCE / 'runway/cli.py').read_text()
        start = text.index("    if action == 'dispatch-get':")
        end = text.index("    if action == 'status':", start)
        text = text[:start] + text[end:]
        old = pi.transform(text, pi.cli_edits(SOURCE), True)
        self.assertEqual(pi.sha(old), pi.PREIMAGES['runway/cli.py'])
        self.cli = self.root / 'runway/cli.py'
        self.cli.write_text(old)
        self.workflow = self.root / 'WORKFLOW.md'
        self.workflow.write_text('old fixture workflow\n')
        for path in (self.cli, self.workflow):
            path.chmod(0o644)
        (self.root / 'index.js').write_text('untouched JS fixture')
        preimages = {**pi.PREIMAGES, 'WORKFLOW.md': pi.sha(self.workflow.read_text())}
        self.mock = patch.object(pi, 'PREIMAGES', preimages)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and p.name != '.api-promo-python.lock'}

    def test_dry_apply_rollback_exact_and_no_host_dispatch(self):
        before = self.snapshot()
        self.assertTrue(pi.deploy(SOURCE, self.root)['dry_run'])
        self.assertEqual(before, self.snapshot())
        pi.deploy(SOURCE, self.root, True)
        text = self.cli.read_text()
        self.assertIn('promo-claim-send', text)
        self.assertNotIn("action == 'dispatch-get'", text)
        self.assertNotIn('Origin-bound native dispatch', self.workflow.read_text())
        self.assertTrue(self.workflow.read_text().startswith('old fixture workflow\n'))
        pi.deploy(SOURCE, self.root, rollback=True)
        pi.deploy(SOURCE, self.root, True, True)
        self.assertEqual(before, self.snapshot())

    def test_interrupted_forward_and_rollback_recover(self):
        real = pi.atomic
        for reverse in (False, True):
            def stop(path, text, mode):
                if path == self.workflow:
                    raise OSError('fixture interruption')
                real(path, text, mode)
            with patch.object(pi, 'atomic', stop), self.assertRaises(OSError):
                pi.deploy(SOURCE, self.root, True, reverse)
            pi.deploy(SOURCE, self.root, True, reverse)

    def test_foreign_change_refuses_all_writes(self):
        pi.deploy(SOURCE, self.root, True)
        self.cli.write_text(self.cli.read_text() + '# foreign\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            pi.deploy(SOURCE, self.root, True, True)
        self.assertEqual(before, self.snapshot())

    def test_preimage_and_collision_refusal(self):
        self.workflow.write_text('foreign preimage')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            pi.deploy(SOURCE, self.root, True)
        self.assertEqual(before, self.snapshot())
