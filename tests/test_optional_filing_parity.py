"""Default exports must not depend on the retired optional filing runtime."""
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from hygiene_fixtures import outputs

SRC = Path(__file__).resolve().parents[1]


class OptionalParity(unittest.TestCase):
    def test_current_default_exports_are_independent_of_retired_optional_filing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            home = root / 'home'
            home.mkdir(mode=0o700)
            tmp = root / 'tmp'
            tmp.mkdir(mode=0o700)
            env = {'PATH': os.environ['PATH'], 'HOME': str(home), 'TMPDIR': str(tmp), 'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_STATE_HOME': str(root / 'state'), 'XDG_CACHE_HOME': str(root / 'cache'), 'PYTHONDONTWRITEBYTECODE': '1'}
            text = subprocess.check_output(['bash', str(SRC / 'install.sh'), '--print'], env=env, text=True, timeout=40)
            current = outputs(text, SRC, home)
            detached = root / 'without-retired-filing'
            def ignore(directory, names):
                excluded = {'.git', 'node_modules', 'dist', 'host', '__pycache__', '.opencode'}
                if Path(directory) == SRC:
                    excluded |= {'lead', 'research', 'archive'}
                if Path(directory) == SRC / 'kits/chief':
                    excluded.add('desk')
                return [name for name in names if name in excluded]
            shutil.copytree(SRC, detached, ignore=ignore)
            after = subprocess.check_output(['bash', str(detached / 'install.sh'), '--print'], env=env, text=True, timeout=40)
            self.assertGreaterEqual(len(current), 22)
            self.assertEqual(outputs(after, detached, home), current)
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
