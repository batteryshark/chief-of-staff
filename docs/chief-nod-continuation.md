# Chief Nod answer continuation

One helper, one private ledger and one answer outbox. No inbound route, Nod callback,
Docket adapter, credential copying or automatic action execution. Installing the
normal helper does **not** itself install/start a service or deliver an answer.
Running a finite helper or adopting a Fleet-managed runner requires the operator's
existing service authority and configured issuer/native authentication. This public
source includes no service-coverage receipt, live enrollment or installation claim.
No second delivery path, presence framework or old-action replay is authorized.

## New decisions: chief-only, linted before creation

Only the current chief may create a decision card. Fresh `chief.json` and native session
Location must match the caller. A shell CLI trusts its process/session identity; this
is not same-UID process isolation. Leads send strategic/decision items through chief_post
or the fresh-pointer chief inbox/plain fallback. No new bus-created principal cards.
Historical card origins, known-ID reads, answer wakes and uncertain attempts stay intact.

Use short plain technical English in ASD-STE100 style. Deterministic lint is not full
language certification or semantic proof of a decision: it checks one question mark
in displayed prose, 2–3 explicit options with one-line outcome descriptions, a named
recommendation and stated no-answer default. No review/discuss/read-this choices.
Input AND final summary + body are limited to600 Unicode code points, including
generated outcomes/recommendation/default. No truncation, added options or inferred
default. --dry-run validates without identity lookup or outward effects. Invalid asks
fail before image publication, continuation intent/binding or HTTP. Ordinary messages
and alerts continue through nod-alert; ask tells informational callers to use it.

## Original-session wake (historical lead bindings retained)

From the current chief's own OpenCode shell context, use simply:

```sh
chief-nod ask /absolute/path/to/question.json
```

New asks bind `OPENCODE_SESSION_ID` and resolve its actual Location through the app's
supported native session list (bounded10,000; absence/ambiguity refuses before POST).
No chief-pointer or cwd guess and no separate registration step. Explicit
`--origin-session`/`--origin-directory` still work; a supplied directory must match
native truth. Optional `--reference` and `--limits` are kept verbatim. When absent,
the helper generates a stable idempotency identity from the exact rendered request,
origin and optional limits/reference, and uses that identity as the private reference.
Identical retries are refused once creation intent exists, even after a lost response;
distinct intentional repeat questions can supply their own new `idempotency_key`.
Outside OpenCode without an explicit session, no real card is sent; dry-run remains
available. No origin is ever inferred from a long-running runner's environment.

The existing runner sends a short DATA wake to **that saved origin**, chief or lead,
after native lookup/status admission checks. It does not use retired Ops for new asks.
Read `chief-nod show REQUEST_ID` for exact saved request/answer/events/optional limits;
never treat the short notification or a choice label as approval. Record the actual
processing receipt before ACK and the actual owner outcome separately. No goal metadata
is patched and no `--goal` flag is sent. This wakes one model turn, not an automatic
resume of a paused native/heartbeat goal. An owned wait still needs its exact original
binding, current objective/hold checks and authorized continuation; manual stop wins.

The new mode is persisted only on new asks. Historical registered cards keep their
original origins, handled/dedup/uncertain states and legacy live-chief routing. No old
unregistered card is swept, rebound or
replayed. A server response reusing an existing registered ID is refused, not migrated.

Historical heartbeat-created cards used `--answer-route heartbeat-bus`; only their
`heartbeat:` idempotency namespace is accepted in this internal mode, and origin flags
are forbidden. They POST without direct registration, retaining journal-only answer
ingest. The installed bus command vector also pins this mode before the subcommand so
an already-loaded native adapter cannot silently select direct routing. Old unscoped
heartbeat calls refuse before POST, never direct-wake. Bus subprocesses strip inherited
`OPENCODE_SESSION_ID`. There is no callback/second answer-delivery path.

## Historical explicit registration (no delivery)

```sh
chief-nod register REQUEST_ID --origin-session ses_ORIGINAL \
  --origin-directory /absolute/original/project --reference PRIVATE_REF \
  --limits 'Exact scope, time/freshness, hands and expiry constraints; no new authority.'
chief-nod status
chief-nod show REQUEST_ID
chief-nod reconcile REQUEST_ID
```

Registration persists the explicit original binding **before** fetching the full
stored request and then its decision. Already-saved answers are therefore included;
fetch failures retain the binding for later reconciliation. The issuer cannot list
requests: only explicitly registered IDs are checked, never a historical scan.
Bindings cannot be silently changed. Backfill is explicit Ops provenance, not Nod
historical metadata. `--already-handled 'actual prior-relay record'` suppresses an
entire request while still fetching its current stored state once. It also suppresses
an already registered request. Never use it to invent an owner outcome.

`show` is a **private full state read**, including request/answer text; do not paste
it into public logs or reports. `status` contains only IDs, states and generic fetch
errors, plus a safe `runner_last_tick` heartbeat. Full exact answer objects (including any server identity/timestamps),
snapshots/digests, original references and limits stay in
`~/.chief-of-staff/nod-continuations/state.json` (0600, directory 0700). Atomic replace,
fsync and a process lock protect concurrent registration, runner and ACK operations.
`CHIEF_NOD_STATE_DIR` overrides this path for isolated fixtures. The state is local
trusted operator data, not cryptographic sender/owner attestation.

New asks automatically bind as above; explicit historical registration retains its
original four-field contract. The mapping and exact creation intent
are saved before POST; the confirmed request ID is saved before immediate GET
reconciliation. A repeated creation key is refused, including after a lost response:
do not accidentally turn unknown creation into another card. `status` exposes
possible-create intents. Recover the actual ID through an authoritative existing
record and `register` it with the original binding; the old possible-create intent
remains as conservative history. Do not POST again merely because an ID is unknown.
`dedupe_key` only covers pending requests and is not this creation safeguard.
New ordinary asks without any resolvable origin refuse safely, rather than creating
another untracked card. Tracked asks reject `callback_url`, avoiding a second delivery path.

## Operator-configured Fleet lifecycle and health

```sh
fleet status chief-nod-answers
chief-nod status
# Owned lifecycle operations, not additional runners:
fleet restart chief-nod-answers
fleet down chief-nod-answers
fleet up chief-nod-answers
```

`run` is finite (1–3600 seconds), checks known IDs no more often than every 30s,
backs failed GETs off to 300s, and never waits/polls for LLM idleness. GETs and the
read-only native status preflight have 15s timeouts; each delivery subprocess has a
30s timeout. An in-progress bounded operation can
finish after the nominal run deadline. Lock contention waits for the current bounded
helper operation. Native CLI work is one synchronous read-only preflight and, only
when ready, one synchronous send; no unbounded child forks.
An operator may configure one service such as `chief-nod-answers` to run the
installed `chief-nod run --seconds 3600 --deliver` helper under its existing
Fleet lifecycle. The commands above assume that separately authorized setup;
this kit installs no LaunchAgent or service enrollment. If configured with
KeepAlive, ordinary process exit restarts the bounded helper; no second supervisor
or parallel runner is needed. `fleet down` intentionally disables later starts;
`fleet up` re-enables them. There is no port or HTTP probe by design. Logs are
`~/.chief-of-staff/nod-continuations/runner.log`, with no answer/token logging.

Health is the exact Fleet process plus `chief-nod status`'s `runner_last_tick`,
updated each completed pass even when all tracked requests are already handled.
`runner_pid` and `runner_code_sha256` attest the PID and helper bytes loaded at process
startup, not the possibly replaced pathname. The installed Python runner keeps loaded
code until its finite exit or ordinary Fleet restart; replacing the file alone is NOT
a reload. Reconcile pending send/create admissions and hold the shared ledger lock
before an owned restart. Existing uncertain events remain uncertain, never requeued.
Normally it advances every 30s; bounded network/CLI work and sleep may delay it.
A tick older than 180s while the machine is awake warrants inspecting this service,
not a new listener or duplicate runner. A heartbeat proves a helper pass, not Nod
reachability, answer delivery, Ops processing or owner execution. Check fetch errors
and outbox states separately. No new short timer/watch is created.

Before activation the already-relayed Docket logon answer, Mac repair approval and
service approval were marked handled from explicit Ops provenance. They are not
replayed; the stale FV card remains unregistered. The principal withdrew the old
Docket card's actual-use-test dependency, not this repair. No synthetic card/test,
replacement acceptance, Windows action or new principal chore is implied. A real
saved-answer-to-Ops wake may be witnessed naturally on a future genuine request;
process/heartbeat/restart checks alone do not claim that live chain.

The actual supported transport is the installed `chief-openchamber session send
--session ... --dir ... --prompt ... --json`. Its own native discovery/authentication
is retained. Immediately before each send, read `~/.chief-of-staff/chief.json` LIVE;
missing/invalid/quiet Chief targets refuse delivery. Original-owner mapping is
independent of that pointer. Never automatically retarget an uncertain/sent event
after a pointer change. `CHIEF_NOD_OPS_POINTER` is for isolated fixtures only.

Before saving send intent, run bounded read-only `session status --session ... --dir
... --json`. Require `status: "ok"`, exact `sessionId` and `directory`, and a known
`sessionStatus.type` (`idle`, `busy`, or `retry`); idle is **not** required. Outage,
timeout or invalid response means this send has not started: keep ready and retry
after backoff. Re-read the LIVE pointer after preflight; a changed target needs a
new preflight on a later attempt. This read cannot eliminate the preflight/send or
pointer-change race. Once intent/send starts, failures still become uncertain and
are not automatically retried. Preflight says nothing about any earlier admission;
it never releases an already uncertain/sent event or treats idle/history absence
as proof that a queued message does not exist.

Canonical pending with individual answers is saved and signalled explicitly as
partial, not canonical approval. Cancellation/expiry without answers produces no
answer event. Exact decision changes and canonical transitions produce distinct
stable event hashes; repeated observations do not. An envelope is data, not new
authority. Stale expiry and original limits are carried unchanged; no authorization
or physical action is inferred. Ops must reconcile related events before acting.

## ACK, owner handling and uncertainty

```sh
chief-nod ack REQUEST_ID EVENT_ID --reference PRIVATE_REF --receipt DURABLE_OPS_RECORD
chief-nod handled REQUEST_ID EVENT_ID --reference PRIVATE_REF --receipt OWNER_OUTCOME_RECORD
```

State meanings:
- `ready`: not dispatched, or a definite local spawn failure; retry permitted.
- `sending`: intent durably saved before launching the CLI.
- `sent`: CLI returned success; **not** proof of consumption or owner handling.
- `uncertain`: timeout, nonzero result, other possible admission, or restart during
  `sending`. **Never automatically resend**, even if the pointer changes.
- `acknowledged`: accountable Ops confirms durable processing record for the exact
  request/event/reference. This prevents delivery replay, not substantive work by itself.
- `handled`: separate actual original-owner outcome is recorded after Ops ACK.

The CLI has no caller admission ID or consumed-ACK interface. For uncertain events,
use supported native session status/messages on the **persisted target** to seek
the exact marker `chief-nod-answer:REQUEST_ID:EVENT_ID`, or an actual own processing
receipt. ACK after durable recording can resolve uncertainty directly. To record an
observed native admission without claiming processing:

```sh
chief-nod resolve REQUEST_ID EVENT_ID --reference PRIVATE_REF \
  --outcome admission-observed --receipt ACTUAL_ADMISSION_EVIDENCE
```

**History absence and idle status do not prove no queued admission.** Leave uncertain
when unresolved. Only an explicit operator reconciliation proving no dispatch may
release it for retry:

```sh
chief-nod resolve REQUEST_ID EVENT_ID --reference PRIVATE_REF \
  --outcome not-dispatched --receipt ACTUAL_NONDISPATCH_EVIDENCE
```

Receipt arguments are references to actual durable records, not helper-generated
proof flags. No exactly-once or automatic unknown-send recovery is promised. Nod's
default terminal retention is 90 days; this helper cannot recover purged answers or
unregistered unknown IDs. Machine sleep and endpoint outages delay observation.

## Minimum processing before useful continuation

On the wake, read/reconcile only the exact event and related existing disposition.
In the selected operational record retain request/event/reference, exact answer/time
(or exact durable event reference), original session/absolute directory, scope/freshness
limits and dedup/uncertain disposition BEFORE ACK or action. A receipt is a real record
reference, not an invented success flag. Preserve the runner as PRIMARY and the existing
uncertain-send rules; this changes Ops workflow, not outbox state semantics.

Then ACK and send the authorized continuation to the original owner promptly. Record
the owner outcome separately. Do not rebuild the whole Plan, migrate history, perform
a portfolio/inbox sweep or reconcile three derived Notes first. If a native save only
accepts a whole document, preserve the read body and make the smallest relevant change
with its supported conflict check; that is not authority to reconstruct everything.
Update affected displays after useful continuation; defer unrelated maintenance to
catch-up/checkpoint, marking any display lag honestly. Never extend a readiness lease
to compensate for bookkeeping. Missing/conflicting correlation blocks only that action.
