# Quota-aware worker dispatch

Use the `runway` tool in OpenCode/OpenChamber. Its `request` is a JSON string. The shell equivalent is `chief-runway --server http://127.0.0.1:PORT` with the same JSON on stdin. The server must belong to the target host. The tool discovers `opencode serve --port`; the CLI can use a single official local service registration. For other startup modes set `OPENCODE_SERVER_URL` or the local routes file's `server`. Read credentials only through the runtime's inherited authentication environment.

## Output

`status` and `usage` answer with a short plain-text table: one line per allowance (left, reset,
BURN, LOW, or PAID), then open attempts and routes. `plan`, `prepare`, `bind` and `finish` return
compact JSON: the choice, the exact dispatch `args`, and one line per alternative. Add
`"format":"json"` to any request only when the raw data is really needed.

## New work

1. Give each authorized job a stable short `job` id. Set `category` to `trivial`, `research`, `implement`, or `hard`, `size` to `small`, `medium`, or `large`, and `directory` to the native worker session/project directory. Optional `checkout` names the source worktree when it differs. Omit it to keep the existing directory-as-work-location behavior (including non-repository directories). Explicit checkout paths are canonicalized and must be existing registered worktree roots in the same Git repository as `directory`; foreign repositories and arbitrary subdirectories are refused. Use a separate existing worktree for each concurrent writer. `writer:false` is only for read-only work, not a way to bypass writer conflicts. Keep the task's category and capability requirements honest.
2. Call `plan` for a preview or `prepare` to reserve dispatch. Example request:

       {"action":"prepare","task":{"job":"trace-boot-chain","scope":"/project","directory":"/project","checkout":"/project/wt/trace-boot","category":"hard","size":"medium","writer":true,"tools":true,"input":["text"],"context":32000}}

3. Dispatch only when `dispatch_allowed:true`. Use the returned `action` and `args` with the `openchamber` tool, adding the complete worker brief as `prompt`. A lead turns a returned `session.create` into its own sub-session instead: `a2a_create` (local, nested, with the title, agent and model), then `session.send` to that session with these args (see the lead prompt). Keep its model, variant, directory, messageId and returnResult. Returned `args.directory` always stays the native session directory: do not replace it with checkout. Explicitly instruct the worker to use the recorded checkout for source tools/commands; Runway records and validates the location but does not redirect tools. Thus a worker can stay nested in `/project` while working in `/project/wt/trace-boot`. Include the saved checkpoint when continuing. Ask the worker to report changed files, checks, remaining work, and any pending commands or external effects. A plan alone is not a reservation.
4. After the tool confirms the worker session, call `{"action":"bind","attempt":"<attempt id>","session":"<session id>"}`. The helper verifies the session's model and directory and revalidates any checkout identity/existence. Writer reservations use checkout (or directory when omitted), so shared native directories do not conflict for distinct worktrees. Scope still controls project preferences; shared provider pool/model caps remain unchanged. Record the job and attempt in the running brief.
5. After the worker finishes, inspect its results and pending/background tools. Call `finish` with `state:"completed"`, `tools_reconciled:true`, and `effects_reconciled:true`. The helper independently checks native idle state, empty inbox and successful outcome. Completion releases concurrency and estimated quota headroom immediately; reservations are admission estimates, not permanent billing.

Repeated `prepare` for the same active job returns `dispatch_allowed:false`. Read `status` and reconcile it; a timeout never proves a worker was not created. Bind a session found after an ambiguous response. Use `finish state:"uncertain"` while its outcome is unresolved. `state:"unsent", confirmed_not_sent:true` is only for a confirmed pre-dispatch failure with no worker created. Never label an ambiguous response unsent.

## Use allowance before its reset

When the user asks to spend a provider's expiring allowance, read `status`. Select a configured route and the exact future-reset window shown there, then:

    {"action":"prefer","scope":"/project","route":"gpt-strong","window":"codex:primary","user_requested":true}

All five keys above are required: `user_requested` must be the JSON boolean `true` (not `user_request`), `scope` must be nonempty, `route` must be a configured route id, and `window` must be the exact window id from that route's observed source in `status` (replace the example values). The CLI directly indexes `scope`, `route` and `window`, so omitting one can raise `KeyError`. The selected window must have a known future `resets_at`; use the observed reset, not an assumed weekday or another window's reset. Source basis: `runway/cli.py`'s `prefer` handler and `runway/ledger.py`'s `Ledger.prefer` (with `runway/policy.py`'s `live_windows`).

Scope is normally the project root; retain it for all jobs in that project. The preference is persisted, scoped to the observed account/window/reset, and expires at that reset. Only the selected window's soft reserve is waived; other windows and reservations still apply. Changed reset identity invalidates the preference. Use `clear-preference` with the same scope to end it early. An expired preference may remain in history but cannot affect a decision.

Use worthwhile already-authorized queued work. A preference neither creates work nor authorizes paid fallback, purchases, reset redemption, account changes, or unnecessary extra reasoning.

## Quota failure and continuation

`plan` AND `prepare` accept top-level `exclude_routes`, a list of exact configured route ids:

    {"action":"prepare","exclude_routes":["gemini-strong"],"task":{"job":"next-slice","scope":"/project","directory":"/project","category":"hard","size":"small","writer":false}}

Exclusions apply only to this request, are retained on an admission, and select the next otherwise eligible route. They do not downgrade the task class, change checkout/directory, mutate configuration, or waive quota, reserve, concurrency or cooldown checks. Unknown ids/malformed lists are errors. All filtered means no selection/no dispatch. Use `plan` with the identical fields for a non-reserving preview; compact rejections explain exclusions and active cooldown deadlines.

`finish` makes a bounded read of the latest five native assistant messages. V2 client 2.0.23 stores provider failures as `type:"assistant", finish:"error", error:{type,message,status?}` with message id, model and time. Only matching-model messages created since admission are considered; tool errors, prose and failed session outcome alone are not provider evidence. Host reader HTTP errors (including inbox/directory failures) never seed cooldowns. No background watcher or provider retry is installed. If native error lookup fails or the message is outside that bounded page, relay the actual provider error explicitly:

    {"action":"report-failure","attempt":"<bound attempt id>","provider_failure":{"message":"Individual quota reached; resets in about120h","observed_at":"2026-10-20T02:23:30Z","key":"stable-failure-or-native-message-id"}}

Alternatively add the same `provider_failure` object to `finish` (e.g. `state:"uncertain"`). Reporting is a routing observation, transparently marked `reported`, NOT identity/credential attestation. No caller-selected route/model is accepted: the bound attempt supplies host/account pool/model. Historical bound quiescent attempts are supported; use the actual historical failure time, not today's clock. Unbound/unsent attempts cannot report a dispatched failure. A report alone never changes attempt state, source ownership, quota reservations or reconciliation flags. Cooldown observation persists independently even if subsequent finish reconciliation is refused; all existing unknown-action/tool/effect guards remain in force.

Known quota/rate-limit wording or a provider status 429 creates a cooldown for that host/pool/model, including model aliases but not other models in the same pool. It blocks preference, burn and ordinary selection in BOTH plan and prepare. Explicit `reset_at` (ISO timestamp) or `retry_after` (seconds, HTTP-date or ISO timestamp) takes precedence; messages such as `resets in120h`, `resets in about120h` and `Retry-After: 60` supply relative hints. Relative deadlines anchor to the original failure time; approximate hints remain labeled approximate. A transient 429 without a reset has a bounded **five-minute** fallback, not a weekly ban. Re-report the same stable `key` (native lookup uses message id); when omitted, a stable hash of error/status/reset hints is used. Same attempt/key retains its first observation/deadline even on repeated finish or later report. Distinct failures need distinct keys. Expired cooldowns are ignored at the next decision without polling; history remains visible in JSON status and active cooldowns in text status.

A 429 alone is ambiguous: it can mean throughput or concurrency. For stale telemetry, refresh only that source once using `tarmac refresh <slug>`; do not loop on refresh or probe other providers. Unknown capacity is a reason to defer automatic admission, not proof of exhaustion.

Omit `provider_failure` from `report-failure` to perform only the same bounded native error observation and cooldown recording, without changing worker state. A missing native error returns `recorded:false`; a host-reader failure is an error, not provider evidence.
Native structured `error.response.body` is also considered (bounded, never echoed), not arbitrary tool output. If a first observation had only the short unknown-reset fallback, richer reset evidence for the same key can replace it once, still anchored to its original observation time; repeated reports cannot slide that deadline forward.

Keep active workers on their current route until they finish or reach a checkpoint. When a worker is quiescent, reconcile background commands, pending tools and external effects. Save:

    {"action":"finish","attempt":"<id>","state":"quiescent","tools_reconciled":true,"effects_reconciled":true,"checkpoint":{"objective":"...","directory":"/project","checkout":"/project/wt/trace-boot","changes":"...","tests":"...","next":"...","side_effects":"none, or exactly what already happened"}}

Then call `prepare` with the same job, scope, directory and optional checkout. Checkpoints must retain both fields when checkout is explicit; legacy checkpoints without checkout remain supported. Bind, continuation and checkpointing revalidate checkout metadata identity/existence, without weakening native session-directory drift checks. It rechecks the old session, chooses from current eligible models, and returns `session.send` for that same session with a fresh stable messageId. Send its checkpoint and next step as the brief, then bind the attempt. A worker that cannot write a checkpoint can be summarized by the chief from its messages, repository state and tool results. Preserve uncertainty explicitly and resolve it before continuation. This is supervised recovery; the helper never interrupts sessions or autonomously replays actions.

Permission/question waits require the outstanding decision. A user-cancelled job is terminal: mark `cancelled` only after idle/tool reconciliation and resume solely under a new authorized job. Running or uncertain attempts never disappear when a timer expires or a process restarts. Use `status` to reconcile them on startup. No background polling agent is installed.

## Registry and limits

Quiescent and terminal attempts hold zero estimated quota, including legacy records;
their checkpoints and history remain intact. Supported `finish` accepts quiescent
to completed/uncertain with current native evidence; do not infer project completion
from a permission/question wait or a successful checkpoint turn. A session reused
by a newer active attempt protects the old checkpoint from terminal relabeling.
For bound `finish uncertain`, Runway independently checks native idle/inbox state.
Verified idle uncertainty releases only estimated quota, never source ownership,
pool concurrency or unknown native effects. Unbound/ambiguous work remains held.
Directory drift is recorded for uncertain quota-only cleanup, not accepted as a
source identity change: completed/checkpoint/bind/resume still enforce their
native-directory checks. This cannot authorize source writes or native replay.
Estimates are clamped per telemetry window/reset to observed remaining; configured
safety reserves still apply. Completed/cancelled cleanup needs native evidence but
not a deleted source worktree; checkpoint, continuation and bind still revalidate it.

`~/.chief-of-staff/runway/routes.json` pins exact host model, variant, task categories, Tarmac source, provider/account, pool, windows, reserve and concurrency cap. Models are checked against the native target catalog, not favorites. Routes for the same source must share a pool/cap. `windows:"all"` conservatively checks every reported window; explicit window ids must all be present and require verified model-group mapping. Brand names do not prove pool identity.

Reservations are fixed percentage heuristics (small 1, medium 3, large 8 points per applicable window), not token estimates. Dispatch bounded slices and reassess at checkpoints. External sessions can consume quota between samples; concurrency limits and reserves reduce risk but cannot guarantee completion. Remote routing and paid API balances are deliberately not admitted by this version. Configure a local registry on each account-owning host before extending remote dispatch.

Fast/Ultrafast surge routes retain the existing source, pool, windows and cap.
`unavailable_transports:["openchamber"]` blocks admission on the current create/send
transport until its selectable-ID validation repair is installed and verified. Do not
remove that marker on catalog visibility alone. Preserve the requested selectable
`id` through dispatch; never normalize it to the underlying catalog `modelID`.
Native model-tool searches for aliases need `all:true`; Runway already reads the
full `/api/model` catalog. Native subagent admission/inherited parent models are
not explicit per-worker model-selection proof; these routes add no alternate transport.
Project surge limits (for example six lanes) remain additional constraints, even
when the existing source-wide cap is higher. No reset or new capacity is assumed.
Acceptance requires explicit selection of ANY enabled picker-offered worker model,
not only these example aliases, with provider/variant validation and actual selected-ID
readback through the repaired supported create/send path. Never normalize to a base ID
or count parent inheritance as selection. No additional model probe is implied here.

## Origin-bound native dispatch (explicitly policy-bound plugin only)

For a **fresh unbound admission**, `{"action":"dispatch","attempt":"<id>","prompt":"<complete brief>"}` uses the existing Runway tool's native context, selected route, immutable input ID and admission body. Do not supply an origin, worker model, agent, policy or ledger transition in agent JSON. The supported native create preserves explicit selection even without a prompt. It creates no goal, performs no switch on an existing session and never uses generic host returnResult.

On a policy-bound plugin Location, fresh `prepare` output is relabeled `action:"runway.dispatch"` with only the reserved attempt ID and a native-dispatch instruction; legacy host returnResult args are removed. This supersedes step 3's generic OpenChamber advice for that fresh integrated path. When options are absent, existing read/admission output is unchanged, but calling the new dispatch path refuses; there is no silent dispatch fallback. Existing session continuations are outside this fresh-worker candidate and are not relabeled or replayed.

This path is disabled unless operator-owned `ctx.options.hostDispatch` supplies current absolute chiefPointerFile and/or rosterFile as applicable, explicit project holdBindings and authorized workerAgent when the reserved route has none. Unchanged chiefSelection binds the chief by its explicit pointer/native directory; unchanged recipientEligibility binds enrolled leads. Foreign/unregistered origins refuse, not fall back; no fixtureMode or agent-name-only chief shortcut. App archive state must be available through the inherited supported OpenChamber connection. Native session state alone cannot establish app archive eligibility. No live options/configuration are installed by the candidate.

Dispatch reserves `host_dispatch` stages with locked compare-and-swap in the existing attempt body, not a new table/lifecycle. The top-level attempt remains uncertain until positive admission acknowledgement. Completion uses one bounded `ctx.session.wait` (not a guessed event type or polling) and collects the exact admitted input/idle interval. The tool returns only to its exact originating message/tool call; no synthetic newest-turn wake is sent. Timeout returns incomplete, not an execution failure. A stopped tool or lost acknowledgement remains uncertain/admitted for owner reconciliation, with no automatic retry or blind result replay. An original caller can explicitly request `{"action":"collect-dispatch","attempt":"<id>"}` to retrieve an admitted result after one bounded wait; its envelope retains the original origin and separately identifies the retrieving tool call. `dispatch-get`, `dispatch-save` and `dispatch-incomplete` are internal owner/CLI operations, blocked as agent requests by the plugin. Regular bind/finish cannot relabel incomplete host dispatch as completed.

The helper does not repair raw UI/host goal loops, make native admission and hold changes atomic, or claim exactly-once delivery after crashes. A hold racing an in-flight admission needs existing cancellation/retraction/reconciliation. Existing continuation/checkpoint workflow remains separate; never run this fresh-worker path on a reused admission. Do not release installed-role/restart gates based on candidate tests.

This integration currently requires the worker's native directory to equal the caller's native Location. It does not relocate callers, implement cross-Location dispatch or change existing leads. An already authorized separate source checkout remains governed by the existing Runway checkout contract.

After normal owner installation, read back effective `ctx.options.hostDispatch`, exact chief/lead eligibility and fresh `prepare` action `runway.dispatch`. The single authorized installed fixture must verify native worker agent/location/selectable `model.id`/variant/no-goal, then exact result `origin` (session/message/tool call), `inputID`, `assistantID` and `idleID`; held/archived/unknown policy must refuse. Missing options must leave ordinary read/admission operations working but the new dispatch path disabled. Source unit tests are not this installed readback.
