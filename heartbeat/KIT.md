# Heartbeat integration source

This is portable source, not an installed pilot, enrollment manifest or deployment
receipt. Runtime setup uses operator-owned private bindings; none are exported here.
README and INTEGRATION describe interfaces and limitations, not live acceptance.

Use `python3 -B scripts/install-heartbeat.py /absolute/private/manifest.json prepare --dry-run`
to preview a disabled-first plan. Initial live installation remains guarded;
`roles` is retired. The maintenance phase updates only already-enabled, exactly
owned runtime/watch entries and refuses topology, goal, hold or options changes.
It never switches a session ID, model, goal or chief pointer.
All replaced bytes/modes and former absence are saved under the chief archive before writes.
Changed goal/hold quotes or owned installed files refuse reinstall rather than blessing drift.

Runtime is installed at `~/.local/share/chief-of-staff/heartbeat`; one watched JS entry
in each opted-in Location imports it with explicit installed options. Version gating selects
the currently paired native host, not the other observed shared-file host. The dispatcher is
hidden from agent catalogs, six steps, Luna medium, heartbeat_resolve only; it reads the
existing short staged chief body (without frontmatter) and bounded current file sections.
Only the exact current chief gets context/close/status/reconcile. Only explicitly named
origins get post; goal tools remain separately enrolled. When explicitly configured,
the attention adapter handles principal-route and urgent chief-route requests, not FYIs,
normal chief judgments or pre-cutover events. It never wakes the chief conversation.
Cards offer custom Review/discuss or Not now choices, not approval; the exact original
limits and journal event/ref/origin remain correlated. Optional post `limits` is stable-key
identity. Summary is at most800 characters plus full record reference; raw original details
stay in the same journal. No generic approve-with-text notes option is auto-added.
Answers are data for current-chief judgment, never an automatic effect or goal resume.
Creation intent/uncertainty never blindly retries. No live card/test alert was sent to enable it.

The existing chief-nod finite runner detects explicitly installed
`~/.chief-of-staff/heartbeat/pilot-options.json` with nodReadEnabled, or takes an explicit
`--heartbeat-options`. Per pass it reads at most four mapped mode:new-bus-only IDs; it never
creates requests, migrates legacy cards, calls legacy deliver for bus IDs, or treats answers
as consent. A Python runner uses its already-loaded functions until its next
natural finite process completion/start or an authorized Fleet restart. Its loaded
code hash/PID are reported in private status. Plain asks bind their actual asking
session automatically; internal heartbeat asks explicitly pin bus-only answer routing.

Goal metadata uses Docket's existing paired adapter, rechecking its own active client record
and current app origin on every call. Only own-wait status/reason/time may change; binding
checks include goal ID/objective/file mode and verbatim Stop conditions + Goal sections.
The app API lacks CAS: final rereads reject observed manual stops, not every simultaneous race.
No goal is paused/resumed during installation. Actual use must still prove each recipient.

`attention` is a source/options-only rollout phase with its own explicit revision receipt;
it preserves local role bytes and defers its first tick to normal30-second host cadence.
It requires unchanged installed topology/goal/hold/enabled bindings. It does not clear
an active claim to perform existing-recipient maintenance. Migration enable/roles still
require the original real-FYI/idle gate. No startup dispatch is forced on watched update.

Dispatcher batches contain at most4 items under the unchanged six-step cap. Task DATA
has one labelled UUID action_handle and business_reference_nonrouting metadata. Resolve
also accepts an exact business ref only if unique inside THAT child's bound batch;
ambiguous/out-of-batch/foreign-session values refuse. Journal/effects always use UUIDs.

Native-idle incomplete batches fall back once into chief inbox with original event/text
and terminal-failure provenance, then finish; neither unresolved items nor existing
uncertain effects are automatically retried. At the3-minute claim deadline, inspect
native activity; only the exact owned heartbeat child can receive ONE durable supported
interrupt(resume:false), followed by bounded idle confirmation before release. Native
errors, unbound/unknown admissions, ownership mismatch or uncertain cancellation remain
parked for chief judgment, NOT age-only stolen. Pre-prompt idle is not terminal work.

At5 minutes, unresolved non-FYI events and covered-but-unadmitted replies are also
included in the read-only bounded chief inbox, with active/error/uncertain provenance
and needsReconciliation. This is visibility, not an answer, ACK, forced chief model
turn or effect retry; omissions are counted. Known reply/Nod intents stay no-replay.
There is no promise of completion while native activity/admission is unknown.

Post-only recipients require explicit operator-owned bindings, independent of goal-wait
enrollment. Preview makes no Location changes. Maintenance must preserve the installed
recipient set and existing holds/goals; it is not a new enrollment or migration route.
Synthetic incremental-profile fixtures live under tests/fixtures/heartbeat, not profiles/.

Fleet's current supported interface only registers LaunchAgents (run/adopt with a label),
not configuration components/timers inside an existing interactive native host. Do not
invent a heartbeat daemon/label or alter another host owner's entry to fake registration.
Any separately registered chief-nod-answers service retains its existing Fleet ownership.

Docket check-ins remain `docket/checkins.py`'s existing PROMPTS + scheduler reconciliation
and the private roster. Their genuine lead prompt is interpreted using reset-reporting;
there is no direct check-in-to-bus hook and no new eligibility loop, timer or stopped lead.

Source integration tests: `node --test heartbeat/integration.test.mjs` and affected Python
tests (including test_chief_nod_continuation and test_heartbeat_install). No phone send,
call, new native fixture or model prompt is part of those tests.
