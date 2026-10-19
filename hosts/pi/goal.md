## Optional Pi goal tracking (lead only)

Requires operator-installed pi-goal-x 0.32.3, independently of worker tools.
An ordinary task doesn't authorize persistent autonomous execution. Bind or create
a goal only on explicit operator request for that objective. If tools are missing,
report that action blocked and continue permitted local work.

Use `get_goal({})`, retrieving omitted criteria with
`get_goal({section: "objective"})`. Verify goal id, objective and execution ownership
before recording progress. Ask the operator to use `/goal-focus` to select an
existing goal and `/goal-resume` when execution takeover is needed. On explicit
creation request, `create_goal({objective: "<full approved objective>"})` creates,
focuses and starts automatic continuation. Set `mode: "sisyphus"` or `token_budget`
only when requested. Preserve all acceptance criteria and ordered steps. Read the
live task schema before `set_goal_tasks` or `update_goal_task`.

Active goals auto-continue after successful execution. Unset `maxAutonomousRuns`
means unlimited; zero disables continuation. Have the operator choose an allowance
in `/goal-settings` before autonomous work. Don't change settings, replenish or
resume without approval. `/goal-resume` renews the allowance period. This doesn't
bound within-run tool loops or other extensions' turns.

On stop, decision or handover, checkpoint LEAD.md and immediately use
`update_goal({status: "paused", reason: "<concrete reason>"})` for an owned active
goal; verify success and stop. `/goal-pause` is the operator control. The distinct
`blocked` policy requires a reason and the same blocker on three consecutive goal
turns. Strict ready/wait contracts require operator `strictExecutionContract`
opt-in; retain the returned wait identity/deadline and never start polling loops.
Don't enable strict mode yourself.

After actual verification, `update_goal({status: "complete"})` enters completion
review when auditing is enabled. Rejection leaves the goal open; inspect the
returned completion state. Auditing is optional and needs no worker package.
Focus is session-local; goals default to `.pi/goals`. Timers need Pi open, and
another session needs explicit execution resume. No successor-session transport
or OpenChamber goal wakeup is supplied. Chief itself must never activate a goal.
