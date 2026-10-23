"""Small offline checks for the memory fix and review-only reset packaging."""
import fnmatch
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('reset_package', ROOT / 'scripts/package-reset-candidate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResetCandidateTest(unittest.TestCase):
    def test_memory_paths_not_arbitrary_relative_edits(self):
        header = (ROOT / 'hosts/opencode.md').read_text().split('\n---\n')[0]
        rules = re.findall(r'action: (\S+)\n    resource: "([^"]+)"\n    effect: (\S+)', header)

        def effect(path):
            return [e for a, r, e in rules if a == 'edit' and fnmatch.fnmatchcase(path, r)][-1]

        for path in ('brief.md', 'open.md', 'principal.md', 'ideas.md', 'models.md',
                     'chief.json', 'inbox/fixture.md', 'archive/inbox/fixture.md',
                     'previews/topic/image.png', '2026-10-22-topic.md', 'PROJECT.md'):
            self.assertEqual(effect(path), 'allow', path)
        for path in ('unrelated.md', 'src/file.py', '.opencode/plan/fixture.md',
                     '../../.local/share/opencode/plans/fixture.md', 'AGENTS.md'):
            self.assertEqual(effect(path), 'deny', path)
        self.assertNotIn('resource: "*"\n    effect: allow', header)

    def test_full_prose_budget_and_no_legacy_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'role.md'
            fragment = root / 'host.md'
            source.write_text('# Lean role\n' + 'ordinary prose\n' * 99)
            fragment.write_text('additional always-loaded host rule\n')
            manifest = {'chief': [str(source)], 'lead': [str(source)]}
            result = module.package(manifest, str(root))
            for text in result.values():
                self.assertEqual(text.split('\n---\n', 1)[1], source.read_text())
                self.assertNotIn('## Host:', text)
                self.assertIn('resource: "*"\n    effect: deny', text)
                self.assertNotIn('{{', text)
            manifest['lead'].append(str(fragment))
            with self.assertRaisesRegex(ValueError, 'lead exceeds prose budget'):
                module.package(manifest, str(root))
            manifest['lead'] = [str(source)]
            source.write_text('packed ' * 100)
            with self.assertRaisesRegex(ValueError, 'exceeds prose budget'):
                module.package(manifest, str(root))

    def test_absent_only_review_output_not_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'role.md'
            source.write_text('# Lean role\n')
            manifest = root / 'sources.json'
            manifest.write_text(json.dumps({r: [str(source)] for r in ('chief', 'lead')}))
            out = root / 'review'
            args = [sys.executable, str(ROOT / 'scripts/package-reset-candidate.py'),
                    str(manifest), '--brief', str(root), '--output', str(out)]
            run = lambda argv: subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(run(args).returncode, 0)
            before = (out / 'chief-reset-candidate.md').read_text()
            self.assertNotEqual(run(args).returncode, 0)
            self.assertEqual((out / 'chief-reset-candidate.md').read_text(), before)
            args[-1] = str(root / '.opencode/agents')
            self.assertNotEqual(run(args).returncode, 0)
            self.assertFalse((root / '.opencode').exists())
