"""Install the two bundled MIT skill packages; never overwrite a foreign package."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'skills/interface-design'
NAMES = ('norman','norman-audit')
RECEIPT = '.chief-interface-skill.json'


def inventory(source):
    result = {}
    for file in source.rglob('*'):
        if file.is_symlink(): raise ValueError('linked skill source refused')
        if file.is_file():
            relative = file.relative_to(source).as_posix()
            result[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not {'SKILL.md','LICENSE'} <= result.keys(): raise ValueError('incomplete skill package')
    return result


def targets(hosts, home):
    for host in hosts:
        if host not in ('opencode','claude','codex'): continue
        base = home / ('.config/opencode/skills' if host == 'opencode' else f'.{host}/skills')
        for name in NAMES: yield SOURCE/name, base/name


def check(source, target):
    expected = inventory(source)
    ancestor = target.parent
    while not ancestor.exists() and not ancestor.is_symlink(): ancestor = ancestor.parent
    if ancestor.resolve() != ancestor.absolute(): raise ValueError('canonical skill ancestry required')
    if target.is_symlink(): raise ValueError('linked skill target refused')
    if target.exists():
        receipt = target/RECEIPT
        if receipt.is_symlink() or not receipt.is_file(): raise ValueError('foreign skill target; not replaced')
        owned = json.loads(receipt.read_text())
        if owned != {'version':1,'files':expected}: raise ValueError('skill version differs; reconcile before replacing')
        actual = inventory(target); actual.pop(RECEIPT,None)
        if actual != expected: raise ValueError('modified skill target; not replaced')
        expected_dirs = {str(parent) for name in expected for parent in Path(name).parents if str(parent) != '.'}
        actual_dirs = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_dir()}
        if actual_dirs != expected_dirs: raise ValueError('foreign skill directories; not replaced')
    return expected


def apply(mode, hosts, home=None):
    if mode not in ('check','install','uninstall'): raise ValueError('invalid skill operation')
    entries = list(targets(hosts, Path.home() if home is None else Path(home)))
    for source, target in entries: check(source,target)
    if mode == 'check': return
    for source, target in entries:
        expected = check(source,target)
        if mode == 'uninstall':
            if not target.exists(): continue
            for name in [*expected,RECEIPT]: (target/name).unlink()
            dirs = sorted((d for d in target.rglob('*') if d.is_dir()),key=lambda d:len(d.parts),reverse=True)
            for directory in dirs: directory.rmdir()
            target.rmdir(); continue
        if target.exists(): continue
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.parent.resolve() != target.parent.absolute(): raise ValueError('canonical skill parent required')
        stage = Path(tempfile.mkdtemp(prefix='.chief-interface-',dir=target.parent))
        try:
            for name in expected:
                out=stage/name; out.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/name,out); out.chmod(0o755 if name.startswith('bin/') else 0o600)
            (stage/RECEIPT).write_text(json.dumps({'version':1,'files':expected},sort_keys=True))
            (stage/RECEIPT).chmod(0o600)
            if target.exists() or target.is_symlink(): raise ValueError('skill target appeared; reconcile')
            stage.rename(target)
        finally:
            if stage.exists():
                for file in sorted(stage.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                    file.rmdir() if file.is_dir() else file.unlink()
                stage.rmdir()


if __name__ == '__main__':
    try: apply(sys.argv[1],sys.argv[2:])
    except Exception: raise SystemExit('Interface skills refused: target is foreign/modified or source invalid; inspect before retrying')
