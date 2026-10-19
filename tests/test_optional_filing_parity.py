"""Only render (--print), never broad installation. Exact pinned 22 outputs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from hygiene_fixtures import outputs, pinned_print

SRC = Path(__file__).resolve().parents[1]


class OptionalParity(unittest.TestCase):
    def test_22_default_outputs_exact_7f0c0ca(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            home = root / 'home'
            home.mkdir(mode=0o700)
            tmp = root / 'tmp'
            tmp.mkdir(mode=0o700)
            env = {'PATH': os.environ['PATH'], 'HOME': str(home), 'TMPDIR': str(tmp), 'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_STATE_HOME': str(root / 'state'), 'XDG_CACHE_HOME': str(root / 'cache'), 'PYTHONDONTWRITEBYTECODE': '1'}
            baseline = root / 'baseline'
            old = outputs(pinned_print('7f0c0ca', baseline, env), baseline, home)
            text = subprocess.check_output(['bash', str(SRC / 'install.sh'), '--print'], env=env, text=True, timeout=40)
            current = outputs(text, SRC, home)
            self.assertEqual(len(old), 22)
            self.assertEqual(current, old)
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
