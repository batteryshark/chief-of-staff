---
name: worktree-safety
description: Safely create or clean repository worktrees, including checkpoint sweeps.
---
# Clean-only worktree lifecycle

No repository/worktrees means N/A; do not introduce git for this procedure.
Inventory git worktree list --porcelain, native metadata and live session locations/state.
Cap: eight secondary worktrees across all owners, main excluded. At eight, safely clean
before another; above eight, sweep now. Other owners' trees count but are protected.
If none is safely removable, serialize/pause instead of forcing. Workers use registered
checkouts inside the project; sessions stay at project root unless the principal asks.
Never strand a session or remove any active cwd.

After merge or explicit abandonment, remove a worker worktree in the same step only if
ours, quiescent and clean. Keep the branch, including abandoned commits. At checkpoint,
park, completion and handover, list retained canonical paths, branches, owners, session
states, reasons and next safe actions in LEAD.md, with sweep time/count or none/N/A.

## Before removal

1. Verify positive ownership and quiescence, including pending tools/effects; unknown is protected.
2. Prove merge into the intended integration ref and record ref/commit, or explicit abandonment.
   Preserve a branch ref for detached abandoned commits before considering removal.
3. Inspect git status --porcelain=v1 --untracked-files=all --ignored and ignored-directory
   contents without following links. Tracked-clean is insufficient; caches/untracked files
   and user data are not automatically disposable. Inspect submodules and locks too;
   retain on uncertainty rather than discarding nested work or unlocking anything.
4. Protect main, other owners, live workers, locked trees and all active session directories.
5. From main, use git worktree remove -- <exact-owned-path> only after those checks. No force,
   branch deletion, broad recursive removal, unlocking or pruning of unknown metadata.
6. On refusal, retain and record why. Re-list actual outcomes. Use a native helper only if
   clean-only and branch-preserving behavior is verified, otherwise use this manual route
   or retain. Never widen permissions to meet the cap.

This authority covers only verified owned disposable trees, not destruction of principal
data, discarding another owner's changes or relaxing a project hold.
