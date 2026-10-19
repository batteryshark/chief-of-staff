"""Courtesy-only absent-create/exact-owned no-op. Not a concurrent OS sandbox.

Immutable, private per-leaf receipts; no marker adoption or policy migration.
Only ordinary current-UID single-link files are ever read or removed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from dataclasses import dataclass

LEDGER = '.config/chief-of-staff/courtesy-ownership'
MAX_RECEIPT = 65536
NONCE = re.compile(r'[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}')


@dataclass(frozen=True)
class Receipt:
    data: dict
    raw: bytes
    stamp: dict


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate courtesy receipt key')
        result[key] = value
    return result


def record_identity(value, mode):
    if (type(value) is not dict or set(value) != {'dev', 'ino', 'uid', 'mode'} or
            any(type(n) is not int or not 0 <= n < 2**64 for n in value.values()) or
            value['uid'] != os.getuid() or value['mode'] != mode):
        raise ValueError('invalid courtesy receipt identity')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_pin():
    """Content-address the narrow helper and every input it executes/renders."""
    root = Path(__file__).resolve().parent.parent
    names = ('scripts/install-courtesy.py', 'scripts/courtesy_owned.py',
             'scripts/courtesy.py', 'practices/upstream-courtesy/body.md',
             'skills/upstream-courtesy/SKILL.md')
    return digest(b''.join(n.encode() + b'\0' + (root / n).read_bytes() + b'\0' for n in names))


def metadata(st, directory=False, system=False):
    valid_type = stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)
    if (not valid_type or st.st_uid not in ({0, os.getuid()} if system else {os.getuid()})
            or st.st_mode & 0o022 or (not directory and st.st_nlink != 1)):
        raise ValueError('unsafe courtesy owner/type/permissions/link count')


def identity(st):
    return dict(dev=st.st_dev, ino=st.st_ino, uid=st.st_uid,
                mode=stat.S_IMODE(st.st_mode))


def read_safe(p):
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as f:
        metadata(os.fstat(f.fileno()))
        return f.read()


class OwnedSkills:
    def __init__(self, home, outputs, owner='default', share_default=False, rollback=False):
        self.home = Path(home)
        if not self.home.is_absolute() or self.home != self.home.resolve():
            raise ValueError('courtesy HOME must be canonical, absolute and nonsymlink')
        # Above HOME: system/current-user dirs; sticky system temp dirs allowed.
        # This supports canonical private test HOME without allowing unsafe HOME dirs.
        for p in reversed(self.home.parents):
            st = p.lstat()
            if st.st_uid == 0 and stat.S_ISDIR(st.st_mode) and st.st_mode & stat.S_ISVTX:
                continue
            metadata(st, directory=True, system=True)
        metadata(self.home.lstat(), directory=True)
        self.outputs = {Path(p): t.encode() for p, t in outputs.items()}
        # Authority comes only from the trusted selected output manifest, never JSON.
        self.allowed_dirs = {str(parent.relative_to(self.home))
                             for p in [*self.outputs, *(self.record_path(p) for p in self.outputs)]
                             for parent in p.parents if self.home in parent.parents}
        self.owner, self.share_default = owner, share_default
        self.run = uuid.uuid4().hex
        self.created = []
        self.dirs = []
        if not rollback:
            self.preflight()

    def record_path(self, p):
        return self.home / LEDGER / (digest(str(p.relative_to(self.home)).encode()) + '.json')

    def validate(self, p):
        try:
            rel = p.relative_to(self.home)
        except ValueError:
            raise ValueError('courtesy target outside HOME')
        if '..' in rel.parts:
            raise ValueError('noncanonical courtesy path')
        metadata(self.home.lstat(), directory=True)
        for parent in reversed(p.parents):
            if parent == self.home or self.home in parent.parents:
                try:
                    metadata(parent.lstat(), directory=True)
                    if parent == self.home / LEDGER and stat.S_IMODE(parent.lstat().st_mode) != 0o700:
                        raise ValueError('courtesy ledger directory must be private 0700')
                except FileNotFoundError:
                    pass
        try:
            st = p.lstat()
        except FileNotFoundError:
            return None
        metadata(st)
        return st

    def read_record(self, p):
        r = self.record_path(p)
        st = self.validate(r)
        if st is None:
            return None
        if stat.S_IMODE(st.st_mode) != 0o600:
            raise ValueError('courtesy receipt must be private 0600')
        fd = os.open(r, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as f:
            current = os.fstat(f.fileno())
            metadata(current)
            if identity(current) != identity(st):
                raise ValueError('courtesy receipt changed during read')
            raw = f.read(MAX_RECEIPT + 1)
        if len(raw) > MAX_RECEIPT:
            raise ValueError('oversized courtesy receipt')
        try:
            data = json.loads(raw, object_pairs_hook=unique_object)
        except (UnicodeError, RecursionError) as e:
            raise ValueError('invalid courtesy receipt JSON') from e
        self.validate_record(p, data)
        return Receipt(data, raw, identity(st))

    def validate_record(self, p, data):
        if (type(data) is not dict or
                set(data) != {'version', 'path', 'owner', 'run', 'sha256', 'file', 'dirs'} or
                type(data['version']) is not int or data['version'] != 1 or
                data['path'] != str(p.relative_to(self.home)) or
                type(data['run']) is not str or not NONCE.fullmatch(data['run']) or
                type(data['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', data['sha256'])):
            raise ValueError('invalid courtesy receipt')
        record_identity(data['file'], 0o600)
        dirs = data['dirs']
        if type(dirs) is not list or len(dirs) > len(self.allowed_dirs):
            raise ValueError('invalid courtesy receipt directories')
        seen = set()
        for d in dirs:
            if (type(d) is not dict or set(d) != {'path', 'file'} or
                    type(d['path']) is not str or d['path'] not in self.allowed_dirs or
                    d['path'] in seen):
                raise ValueError('invalid courtesy receipt directory')
            seen.add(d['path'])
            record_identity(d['file'], 0o700)
        if data['owner'] == self.owner:
            wanted = self.outputs[p]
        elif self.share_default and data['owner'] == 'default':
            from courtesy import skill
            wanted = skill().encode()
        else:
            raise ValueError('courtesy owner collision: ' + str(p))
        if data['sha256'] != digest(wanted):
            raise ValueError('unsupported courtesy policy migration; preserve and reconcile')

    def check(self, p, expected):
        st = self.validate(p)
        rec = self.read_record(p)
        if st is None:
            if rec is not None:
                raise ValueError('missing owned courtesy leaf; reconcile receipt manually')
            return None
        if (not rec or identity(st) != rec.data['file'] or
                digest(read_safe(p)) != rec.data['sha256']):
            raise ValueError('unowned or modified courtesy leaf: ' + str(p))
        return rec

    def preflight(self):
        return {p: self.check(p, text) for p, text in self.outputs.items()}

    def parents(self, p):
        for d in reversed(p.parents):
            if self.home in d.parents:
                self.validate(d / '.courtesy-type-probe')
                try:
                    d.mkdir(mode=0o700)
                except FileExistsError:
                    metadata(d.lstat(), directory=True)
                else:
                    self.dirs.append((d, identity(d.lstat())))

    def exclusive(self, p, data):
        self.validate(p)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)  # Only this newly created descriptor, never existing files.
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
                return identity(os.fstat(f.fileno()))
        except BaseException:
            # Caller retains/refuses any incomplete file, never marker-unlinks it.
            raise

    def install(self):
        self.preflight()  # ALL selected leaves before even ledger directory creation.
        try:
            for p, text in self.outputs.items():
                if self.check(p, text):
                    continue
                start = len(self.dirs)
                self.parents(self.record_path(p))
                self.parents(p)
                self.check(p, text)
                self.exclusive(p, text)
                rec = dict(version=1, path=str(p.relative_to(self.home)), owner=self.owner,
                           run=self.run, sha256=digest(text), file=identity(p.lstat()),
                           dirs=[dict(path=str(d.relative_to(self.home)), file=i)
                                 for d, i in self.dirs[start:]])
                raw = (json.dumps(rec, sort_keys=True)+'\n').encode()
                stamp = self.exclusive(self.record_path(p), raw)
                # No receipt commit means unknown state: never force-clean that leaf.
                self.validate_record(p, rec)
                self.created.append((p, Receipt(rec, raw, stamp)))
        except BaseException:
            self.rollback_created()
            raise
        return self.run

    def same(self, p, rec):
        st = self.validate(p)
        return st is not None and identity(st) == rec['file'] and digest(read_safe(p)) == rec['sha256']

    def prune(self, dirs):
        for d, expected in reversed(dirs):
            try:
                if str(d.relative_to(self.home)) not in self.allowed_dirs:
                    raise ValueError('receipt directory outside courtesy ancestor allowlist')
                self.validate(d / '.courtesy-type-probe')
                metadata(d.lstat(), directory=True)
                if identity(d.lstat()) == expected:
                    d.rmdir()  # Nonempty directories/user data are retained.
            except (OSError, ValueError):
                pass

    def remove(self, p, rec):
        self.validate_record(p, rec.data)
        if rec.data['owner'] != self.owner or not self.same(p, rec.data):
            return False
        # Exact bytes AND inode/owner/mode, not semantic JSON equality. Do this
        # before leaf unlink, also during failure cleanup. Not filesystem CAS.
        if self.read_record(p) != rec:
            return False
        p.unlink()
        if self.read_record(p) == rec:
            self.record_path(p).unlink()
        return True

    def receipt_dirs(self, rec):
        return [(self.home / d['path'], d['file']) for d in rec.data['dirs']]

    def rollback_created(self):
        # Validate every committed creation before the first cleanup mutation.
        try:
            for p in self.outputs:
                self.read_record(p)
            for p, rec in self.created:
                self.validate_record(p, rec.data)
        except (OSError, ValueError):
            return
        for p, rec in reversed(self.created):
            try:
                if self.remove(p, rec):
                    self.prune(self.receipt_dirs(rec))
            except (OSError, ValueError):
                pass

    def uninstall(self):
        records = self.preflight()
        for p, rec in records.items():
            if rec and rec.data['owner'] == self.owner:
                if not self.remove(p, rec):
                    raise ValueError('courtesy leaf/receipt changed; reconcile manually')

    def rollback(self, run):
        # Unlike uninstall, retain edited/replaced leaves and their receipts.
        if type(run) is not str or not NONCE.fullmatch(run):
            raise ValueError('invalid courtesy rollback run')
        records = {p: self.read_record(p) for p in self.outputs}
        for p, rec in reversed(list(records.items())):
            if rec and rec.data['run'] == run and rec.data['owner'] == self.owner:
                try:
                    if self.remove(p, rec):
                        self.prune(self.receipt_dirs(rec))
                except (OSError, ValueError):
                    pass
