Never pass a `directory` other than your own to `a2a_create`: that makes a top-level session,
which goal mode doesn't wait for. When parallel workers would touch the same repository, create a
git worktree inside the project (for example `wt/<name>`) and tell the worker to work there.
Before creating one, apply the lead core's Worktree hygiene count and hard cap of 8;
do not move sessions. Merged or explicitly abandoned worktrees are cleaned in the same step.
