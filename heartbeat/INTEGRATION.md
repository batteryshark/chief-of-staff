# Tiny kit integration contract — prepared, NOT deployed

No kit scripts, global config, live goal, Nod card, phone notification or call was changed/sent by this work.
Principal-facing messages/notifications go through **Nod only**. Calls belong to **Voicestack**, not this adapter;
this task authorizes no calls. Agent-to-agent answer admission below is not a principal notification.

## 1. One native plugin entry and current records

Use ONE operator-installed watched `.opencode/plugins/*.js` wrapper based on
`watched.js`; import `setupHeartbeat` from this source. Private proof fixtures are not shipped.
Do not also configure the directory-package entry. The kit installer owns eventual placement and options.
Keep chief session/model/agent explicit. Native methods return `.data`; step-cap validation runs at dispatch
because configured agents can register after user-plugin setup. No goal mode on dispatchers, no automatic parent result.

Required production options (all paths/IDs explicitly supplied by the integrator, no discovery guesses):

- `memoryRoot`: existing chief-memory heartbeat subdirectory; only `events.jsonl` is the business journal.
- `chiefPointerFile`: exact existing `chief.json` path. Read/validate session + absolute directory against native
  Session.Info at dispatch and chief-only authorization/context; reread before child admission. Never rewrite it.
  Only tests use `fixtureMode:true`, `chiefSessionID`, `chiefDirectory` as the explicit fixed override.
- Bounded dispatcher `agent`, authorized cheap `model`. Journal claims serialize instances/hosts; no coordinator.
- `chiefInstructionsFile`: current installed/approved chief instructions, not draft runtime.
- `standingSections`: `{file,heading,maxChars}` selections from EXISTING chief files. Read at dispatch AND resolution.
  Complete paragraphs are selected (default 3,000 chars/section; max 4,000, aggregate JSON <=12,000); omitted paragraph
  counts and exact source refs are supplied explicitly. Large principal/brief files no longer fail a whole-file cap.
  `standingFiles` remains a bounded-prefix fallback for small files, not a massive prompt. No hand-maintained
  production policy JSON. `decisionsFile` remains fixture-only. `decision` refs are `file + '#' + literal heading`.
- `originSessions`: explicit enabled origin session IDs; native Session.Info supplies the actual directory.
- `goalSessions`: ONLY separately reviewed goals; live migration is not authorized by this task.
- `holdBindings`: keyed by exact origin directory. Existing simple arrays remain supported; production lane binding
  is `{global:[...],lanes:{mac:[...],pc:[...]}}`, each entry `{file,heading,allowedQuote}` referencing EXISTING records.
  `clearQuote` remains a legacy fixture alias. The quote is the reviewed ALLOWED STATE FOR THIS LANE, not an invented
  all-clear approval; it may retain one lane's hold while allowing independent authorized work.
  Include known universal/hard-stop sections in `global`, and only the enrolled lane's actual scoped sections in
  that lane. Do NOT bind the entire mixed project/progress log as a global clear state. Missing/unreviewed lane or
  changed relevant section refuses auto-resume. Changes to other lane sections/unrelated progress do not block Mac.
  If actual records cannot support that selection, agree exact existing snippets with the owner before pilot;
  don't rewrite holds, infer permission from silence, or auto-switch a held goal into another lane.

`heartbeat_resolve({event,route,text,decision,quote})` accepts a useful contextual covered reply, not just whole-policy
regurgitation. For covered replies, `decision` must be a current standing-file key and `quote` a literal supporting
excerpt in that file. Response + evidence are recorded together. Semantic coverage still depends on the bounded
dispatcher role; citing a real file does NOT make new judgment authorized. Novel/unclear authority stays chief or principal.
Coordinated chief-file writes are still an integrator concern; dispatcher tools cannot directly edit those files.

## 2. Answer delivery and waiting goals

Chief-only `heartbeat_close({event,text})` records the answer, attempts targeted delivery once, then closes only
after admission. Uncertain delivery remains visible and never blindly replays. Admission is not owner completion.
The same origin/event is used for a matching registered goal wait. New waits on answered/closed events refuse.

`chief_wait({event,lane})` is origin-gated and pauses ONLY that origin's active goal. Use lane="" only for a reviewed
simple-array binding; scoped production waits name their reviewed lane. It saves exact goal ID/objective/budget,
event, unique reason/timestamp and hold-section evidence before the app write. It never aborts active/nested workers.
Resume requires its own confirmed wait, unchanged ID/reason/timestamp/objective/budget, clear unchanged bound holds,
and a fresh app goal read immediately before the resume intent/write. It changes status/reason/timestamp only;
objective, budget and usage/stop counters are not reset. Later observed manual pause/stop/change is rejected.

**Concrete remaining race:** a UI stop or record hold can arrive after those reads but before the app POST or native
answer admission. The supported metadata API has no compare-and-swap. The adapter cannot atomically exclude that
race, nor observe a hold that appears and disappears between reads. No host patch/lock framework is claimed.
Review this limitation and the actual existing hold bindings before enabling any live goal.

### Existing Docket TIME wait — no chief question

Schedule with the ALREADY RUNNING Docket service/tool, pinned to your exact native session/directory. Example shape:
`docket timer --in 20m --session ses_ORIGIN --directory /ACTUAL/PROJECT --reason 'resume approved task' --context
'{"lane":"mac","reference":"existing approved task"}' --by lead-label --json`. Setter labels are self-reported,
not authentication. No service start, Docket lead restart, new scanner or model wait-loop.

1. Read the returned real one-shot timer/alarm ID, then call `chief_wait_time({item:"dkt_...",lane:"mac"})` and end.
   It reads that exact item through the existing Docket client (`docketSource`: explicit installed checkout/client),
   checks pending/future state + exact target/directory, records item/time/context + scoped hold/goal binding,
   then pauses only its own active goal. No bus `post` or fictitious unanswered question is created.
2. Docket delivers its ordinary wake through its existing paired host. The lead interprets that genuine wake and
   explicitly calls `chief_resume_time({item:"dkt_..."})`. No prompt/context hook auto-parses incoming text to resume.
3. Resume reads the known Docket record, validates pinned identity/time/context, and requires its stable native
   `receipt.admission_id` as an actual user message ID in THIS session's context. Early/cancelled/wrong-target/fake
   text refuses. It then uses the SAME own-wait/hold/final-goal checks as bus answers, preserving counters/stops.
   It does NOT send another prompt: the useful work continues in the already-admitted Docket turn.

If Docket/read/context is unavailable, refuse and report the narrow gap; do not restart it, poll a model, guess
sender identity or release a manual stop. A legitimate scheduled Docket notice may itself arrive after a later
manual stop; explicit resume must refuse that stop, not interpret the notice as authority to continue.
Copy `docket-read.py` beside `timed-wait.mjs` (also when bundling). It uses `python3 -B` and the existing supported
Docket client; no bytecode/source/credential writes or raw DB reads. One-shot timers/alarms are covered; recurring
occurrence enrollment is intentionally not invented. The optional onTimedResume callback is fixture instrumentation,
not required by production; do NOT copy the proof-only callback that pauses after observing a successful resume.

### Useful status/milestone filing without another ledger

Dispatcher `route:"filed"` stores a brief status/milestone/FYI summary on the original journal event, needing no reply.
`covered` is for actual standing-authority answers. Both remain visible in `Bus.recent()` / current-chief context:
latest per owner/ref, timestamps, original source/session/directory, explicit excerpts/omissions and filed summaries.
Reading is not ACK. New owner events outrank older brief summaries as FACTS, not permission to lift holds/decisions.
This is a useful durable chief record/digest, not a claim that brief.md has been silently updated.

Tiny coordinated brief seam, if desired: existing CURRENT CHIEF conversation alone reads each full event, then uses
its normal conflict-checked file patch to update only the relevant brief status line with `{eventID,owner,ref,at,summary}`.
Require the expected current file body/block/hash and validated chief binding, preserve principal decisions/holds,
and refuse stale/conflicting patches. Dispatcher never writes brief concurrently. No second file owner, second
business ledger, new coordinator or automatic whole-file rewrite is introduced. This brief-file adapter is NOT
implemented/claimed ready here; journal + derived context is the implemented status source.

## 3. Nod create adapter: new requests ONLY

`NodAdapter(bus,{command:[ABSOLUTE_INSTALLED_CHIEF_NOD],run?})` uses the existing installed helper and its own
inherited authentication. It never reads/copies/prints issuer tokens. Source contract was read from kit
`scripts/chief-nod`: `ask` reads request JSON on stdin and prints `sent request_id=...`.

Chief-only routing supersedes automatic principal attention creation (22Oct2026).
`Bus.resolve` maps new legacy `principal` input to `chief`; `heartbeat_resolve` never
invokes creation callbacks. `attentionDelivery` returns chief-judgment-pending without
transport or journal mutation. `NodAdapter.ask` refuses before any intent/binding.
Only current chief uses linted `chief-nod ask` after reviewing the original item.
The existing chief inbox/plain fallback remains. No pending effect is approved or dropped.
Historical journal rows, card origins, request mappings and uncertain effects remain
unchanged, readable and eligible for their existing known-answer reconciliation below.

## 4. Exact tiny kit-script change + answer feed

The existing `chief-nod decision` prints a lossy text view. Add ONE private read-only JSON variant to kit
`scripts/chief-nod` (NOT changed here), using its existing `call` authentication and request validation:

```python
def decision_json(args):
    rid = urllib.request.quote(args.request_id, safe='')
    print(json.dumps(call('GET', f'/api/v1/requests/{rid}/decision')))
    return 0

# in main(), before parse_args:
d = sub.add_parser('decision-json', help='PRIVATE exact known-request answer JSON; no delivery')
d.add_argument('request_id')
# dispatch: decision_json(args) when args.cmd == 'decision-json'; leave every old branch unchanged
```

Then feed ONLY `nod-request` rows marked `mode:new-bus-only` in this journal to `NodAdapter.check(requestID)`.
It refuses unknown/legacy IDs BEFORE running the command. Reuse the existing runner's bounded cadence/known-ID
processing with an explicit opt-in bus branch; no new daemon, request scan or historical backfill. Keep a bounded
per-pass count (e.g. four known IDs); do not delay urgent bus dispatch behind a long read sweep.
The current helper runner must NEVER call its legacy `deliver()` for those new bus rows. Old cards keep their
existing ledger, origin, pointer lookup and continuation unchanged; no rebinding or migration.

Alternatively an already-authenticated kit read can feed the explicit operator-only seam:

```sh
node heartbeat/nod-ingest.mjs --options /ABSOLUTE/KNOWN/heartbeat-options.json --trusted-kit-input
# stdin: {"requestID":"NEW_KNOWN_ID","answer": EXACT_AUTHENTICATED_NOD_JSON}
```

The flag is an operator contract, not authentication or a public callback. This command must not be exposed as an
unauthenticated endpoint/model tool. `ingestNodAnswer` validates request ID against its saved NEW bus mapping,
preserves exact raw answer/timestamps/origin/limits and stable dedup hash, then queues chief judgment on the SAME
original event (so an existing wait remains correlated). No answer means no approval. Partial/pending answers are
DATA, not canonical approval. Changes after closure require reconciliation, not automatic reopen or replay.
Ingest does NOT send, wake a goal, satisfy hands, or make a decision. Chief reviews the saved answer/limits and
uses the normal guarded answer path. No receipt ceremony/second decisions database is added.

## 5. Explicit recovery options

```sh
node heartbeat/recover.mjs --options /ABSOLUTE/KNOWN/heartbeat-options.json status
# Only after independently confirming no active writer, using the reported exact inode:
node heartbeat/recover.mjs --options /ABSOLUTE/KNOWN/heartbeat-options.json unlock-confirmed-no-writer INODE NOTE
```

No config/pointer guessing. Status derives claims, reply uncertainty and new Nod creation uncertainty from the
journal. Exact-chief `heartbeat_reconcile` retains its bounded native-idle check; unbound create ambiguity remains
manual. No stale lease stealing, history-absence-as-proof or automatic uncertain replay.

## Verification boundary

Native model-invoked wait -> recorded-file hold binding -> explicit chief answer -> original lead receipt -> close
passed in the SAME fixture seam. No standalone control proof/core activation was repeated. Nod create/check/ingest
and useful covered replies were tested with local stubs/current fixture files, NOT live phone/Nod delivery.
Native covered-answer delivery, kit `decision-json`/runner feed, production record selections and live-stop race
review are remaining integration steps. Actual production scheduling/load deadlines are still unmeasured.
