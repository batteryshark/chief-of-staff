"""Destination preflight reusable by scoped installers, not a raceproof sandbox."""
from pathlib import Path
import stat


class DestinationRoot:
    """Resolve the selected root once; reject all symlinks *below* that root.

    Root aliases (including macOS /var -> /private/var) are permitted. Targets
    must be lexical descendants of the canonical root, without '..'. Existing
    child ancestors must be real directories and leaves must not be symlinks.
    Call validate_all on the complete target set before any filesystem mutation.
    Concurrent path replacement after preflight and per-file I/O failures are
    outside this guard's guarantee; this is not a whole-install transaction.
    """

    def __init__(self, selected_root):
        try:
            self.path = Path(selected_root).resolve()
        except RuntimeError as e:
            raise ValueError('cannot resolve destination root') from e
        if self.path.exists() and not self.path.is_dir():
            raise ValueError('destination root must be a directory')

    def validate_all(self, targets):
        for target in targets:
            target = Path(target)
            try:
                relative = target.relative_to(self.path)
            except ValueError:
                raise ValueError(f'destination escapes selected root: {target}')
            if not relative.parts or '..' in relative.parts:
                raise ValueError(f'destination is not a child of selected root: {target}')
            current = self.path
            for index, part in enumerate(relative.parts):
                current = current / part
                try:
                    mode = current.lstat().st_mode
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(mode):
                    raise ValueError(f'symlinked destination below selected root: {current}')
                if index < len(relative.parts) - 1 and not stat.S_ISDIR(mode):
                    raise ValueError(f'destination ancestor is not a directory: {current}')
