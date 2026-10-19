# Quota-aware worker dispatch

Use the `runway` tool in OpenCode/OpenChamber. Its `request` is a JSON string. The shell equivalent is `chief-runway --server http://127.0.0.1:PORT` with the same JSON on stdin. The server must belong to the target host. The tool discovers `opencode serve --port`; the CLI can use a single official local service registration. For other startup modes set `OPENCODE_SERVER_URL` or the local routes file's `server`. Read credentials only through the runtime's inherited authentication environment.

## Output

`status` and `usage` answer with a short plain-text table: one line per allowance (left, reset,
BURN, LOW, or PAID), then open attempts and routes. `plan`, `prepare`, `bind` and `finish` return
compact JSON: the choice, the exact dispatch `args`, and one line per alternative. Add
`"format":"json"` to any request only when the raw data is really needed.

## New work

1. Give each authorized job a stable short `job` id. Set `category` to `trivial`, `research`, `implement`, or `hard`, `size` to `small`, `medium`, or `large`, and `directory` to the exact worker checkout. Use a separate existing worktree for each concurrent writer. `writer:false` is only for read-only work. Keep the task's category and capability requirements honest.
2. Call `plan` for a preview or `prepare` to reserve dispatch. Example request:

       {"action":"prepare","task":{"job":"trace-boot-chain","scope":"/project","directory":"/project/worktree","category":"hard","size":"medium","writer":true,"tools":true,"input":["text"],"context":32000}}

3. Dispatch only when `dispatch_allowed:true`. Use the returned `action` and `args` with the `openchamber` tool, adding the complete worker brief as `prompt`. A lead turns a returned `session.create` into its own sub-session instead: `a2a_create` (local, nested, with the title, agent and model), then `session.send` to that session with these args (see the lead prompt). Keep its model, variant, directory, messageId and returnResult. Include the saved checkpoint when continuing. Ask the worker to report changed files, checks, remaining work, and any pending commands or external effects. A plan alone is not a reservation.
4. After the tool confirms the worker session, call `{"action":"bind","attempt":"<attempt id>","session":"<session id>"}`. The helper verifies the session's model and directory. Record the job and attempt in the running brief.
5. After the worker finishes, inspect its results and pending/background tools. Call `finish` with `state:"completed"`, `tools_reconciled:true`, and `effects_reconciled:true`. The helper independently checks native idle state, empty inbox and successful outcome. Completion releases concurrency; its estimated charge remains until telemetry observes the completed work.

Repeated `prepare` for the same active job returns `dispatch_allowed:false`. Read `status` and reconcile it; a timeout never proves a worker was not created. Bind a session found after an ambiguous response. Use `finish state:"uncertain"` while its outcome is unresolved. `state:"unsent", confirmed_not_sent:true` is only for a confirmed pre-dispatch failure with no worker created. Never label an ambiguous response unsent.

## Use allowance before its reset

When the user asks to spend a provider's expiring allowance, read `status`. Select a configured route and the exact future-reset window shown there, then:

    {"action":"prefer","scope":"/project","route":"gpt-strong","window":"codex:primary","user_requested":true}

Scope is normally the project root; retain it for all jobs in that project. The preference is persisted, scoped to the observed account/window/reset, and expires at that reset. Only the selected window's soft reserve is waived; other windows and reservations still apply. Changed reset identity invalidates the preference. Use `clear-preference` with the same scope to end it early. An expired preference may remain in history but cannot affect a decision.

Use worthwhile already-authorized queued work. A preference neither creates work nor authorizes paid fallback, purchases, reset redemption, account changes, or unnecessary extra reasoning.

## Quota failure and continuation

A 429 alone is ambiguous: it can mean throughput or concurrency. Inspect the structured worker failure and the mapped quota windows. For stale telemetry, refresh only that source once using `tarmac refresh <slug>`; do not loop on refresh or probe other providers. Unknown capacity is a reason to defer automatic admission, not proof of exhaustion.

Keep active workers on their current route until they finish or reach a checkpoint. When a worker is quiescent, reconcile background commands, pending tools and external effects. Save:

    {"action":"finish","attempt":"<id>","state":"quiescent","tools_reconciled":true,"effects_reconciled":true,"checkpoint":{"objective":"...","directory":"/project/worktree","changes":"...","tests":"...","next":"...","side_effects":"none, or exactly what already happened"}}

Then call `prepare` with the same job, scope and directory. It rechecks the old session, chooses from current eligible models, and returns `session.send` for that same session with a fresh stable messageId. Send its checkpoint and next step as the brief, then bind the attempt. A worker that cannot write a checkpoint can be summarized by the chief from its messages, repository state and tool results. Preserve uncertainty explicitly and resolve it before continuation. This is supervised recovery; the helper never interrupts sessions or autonomously replays actions.

Permission/question waits require the outstanding decision. A user-cancelled job is terminal: mark `cancelled` only after idle/tool reconciliation and resume solely under a new authorized job. Running or uncertain attempts never disappear when a timer expires or a process restarts. Use `status` to reconcile them on startup. No background polling agent is installed.

## Registry and limits

`~/.chief-of-staff/runway/routes.json` pins exact host model, variant, task categories, Tarmac source, provider/account, pool, windows, reserve and concurrency cap. Models are checked against the native target catalog, not favorites. Routes for the same source must share a pool/cap. `windows:"all"` conservatively checks every reported window; explicit window ids must all be present and require verified model-group mapping. Brand names do not prove pool identity.

Reservations are fixed percentage heuristics (small 1, medium 3, large 8 points per applicable window), not token estimates. Dispatch bounded slices and reassess at checkpoints. External sessions can consume quota between samples; concurrency limits and reserves reduce risk but cannot guarantee completion. Remote routing and paid API balances are deliberately not admitted by this version. Configure a local registry on each account-owning host before extending remote dispatch.
