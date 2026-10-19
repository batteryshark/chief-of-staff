"""Exact-position, hash-pinned additive normalization; never strip by keyword."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

SRC = Path(__file__).resolve().parent.parent


def outputs(text, source, home):
    text = text.replace(str(Path(source).resolve()), '<SOURCE>').replace(str(home), '<HOME>')
    return dict(part.split('\n', 1) for part in text.split('=== ')[1:])


def without_hygiene(outputs):
    gold = json.loads((SRC / 'tests/hygiene-default-insertions.json').read_text())
    result = dict(outputs)
    for path, spans in gold.items():
        text = result[path]
        for start, end, digest in reversed(spans):
            assert hashlib.sha256(text[start:end].encode()).hexdigest() == digest, path
            text = text[:start] + text[end:]
        result[path] = text
    return result


def pinned_print(ref, root, env):
    root = root.resolve()
    root.mkdir()
    data = subprocess.check_output(['git', 'archive', ref], cwd=SRC, timeout=20)
    # Trusted repository commit, isolated directory, no checkout/reset/worktree.
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(root)
    return subprocess.check_output(['bash', str(root / 'install.sh'), '--print'],
                                   env=env, text=True, timeout=25)
