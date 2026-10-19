# Optional native desk host adapter (source only)

Nothing here activates a plugin or installs agents. `makePlugin({enabled:true,
home,python})` is a host factory for a later reviewed local entry. `python` must
be an explicit absolute interpreter. Default/standalone/domain policy is unchanged.
`install-desk.py --native-artifacts` stages inert files under desk/native-runtime,
not an auto-discovered plugin entry, live settings or new config/identities.
`catalog.mjs` describes deny-first dedicated roles; chief event permissions are
additive to the existing chief, not replacement of its conversation/voice catalog.

`fixture-entry.mjs` now supplies a private default-export SOURCE entry and strict
fixture-only composition; `fixture-config.mjs` supplies fixed inert descriptors.
See `FIXTURE.md` and `OPERATOR.md`: pending runtime bindings register safely,
operations refuse until operator completion; actual-context capture is private and
bounded. The operator collector/writer, metadata bootstrap, fixed captured-c canary
and bounded evidence path are staged SOURCE. Offline fakes are NOT native proof or
permission to activate; independent source review and native authorization remain.

## Operator-only configuration contract (NOT seeded or written by the adapter)

The eventual host owns `desk/native-host.json` alongside the existing authoritative
store/registry/routes. No model tool can read/edit/administer these through this
adapter. Trusted administration must quiesce the adapter and use the shared writer
guard for source/rule/route/authority mutations. This is not an OS sandbox against
a malicious same-user process/plugin or an unrelated agent with unrestricted shell.
Do not install in a host where other model tools can mutate its host state.

Version 1 requires enabled, distinct desk_agent/chief_agent, home_nativeProjectID
(actual Core Session.Info.projectID), home_projectId (managed Knowledge namespace),
projects mapping each registered project to enabled, lead_agent, nativeProjectID
and projectId. Core IDs and Knowledge IDs are separate contracts, never inferred
from basename. Duplicate Knowledge namespaces fail closed. `note_create:true` and
`overview_create:true` are explicit operator creation gates; missing means pending.
No existing manual lead Note is automatically adopted/transferred, and no fictional
fixture is referenced. This phase supplies no configuration/registry administration
or binding-creation tool. Do not copy Example pairing, discover tokens or pair anew.

`knowledge` requires exact installed generated source path, its sha256 and a
descriptor_sha256 from `descriptorHash` (description, JSON schema and options).
Capture occurs inside native transforms, wrapping raw generic executors for denial.
Invocation verifies source/descriptor and requires a one-use private host ticket
to be consumed by the registered wrapper. This does not depend on executor function
equality across the native bridge. The ticket is an internal raw-input capability,
not metadata/ToolContext proof, and is stripped before the captured executor call.
The actual caller context is matched and unchanged. Disabled/missing/replaced
managed capability fails closed if the guarded callback is not entered.
The original executor gets actual tool context; it owns callback auth internally.
No token/environment credential is inspected or redirected. Wrapper schemaVersion
1/ok/action/data is required; native UI endpoints are never substituted for CAS.

## Typed model tools

- lead: desk_report(report), exact core schema. Host captures actual tool context,
  current native agent/project/location, registry and fresh desk route. Host-minted
  input ID/body/epoch/caller provenance commits before native prompt admission.
- desk: desk_inbox(inputId) reads exact owned active native input, not c.messageID,
  newest message, model proof flags or metadata-as-authentication. Missing/compacted
  record remains uncertain. Current native sender/desk/project/epoch are rechecked
  inside filing transaction. No generic final watcher: model final stays in desk.
- desk: desk_project_sync(receiptId) performs only host-built owned status/overview
  Note operations; full unrelated list contents remain host-side.
- desk: desk_propose(receiptId,ruleId,'apply-exact-recorded-rule') rechecks the EXISTING
  full-report exact-hash rule. No classifier/new reusable policy grants authority.
- chief: desk_decision(project,sourceReceipt,itemKey,expectedRevision,state,
  decisionText), states open/closed/revoked. Current actual chief, project/source,
  revision and tool provenance commit atomically. This is chief judgment, NOT
  principal approval or an authenticated principal ask; no Todo mutation follows.

The private stdin bridge has a closed operation allowlist, no public --verified,
operator registration, generic shell or credentials. One fixed child per call;
no inherited auth environment, shell/PATH lookup or unbounded subprocess queue.
5s child deadline, 256KiB request/output bound; on failure never claim ACK/replay.
SQLite FULL and writer guard serialize report, native actions and transition audit.
Core decision_update now checks current seq under BEGIN IMMEDIATE + writer guard.

## Effects and recovery

### Unary SDK observation and interruption

`boundary.mjs` bounds observation, NOT the underlying native RPC: installed
session functions are unary and ignore RequestOptions. No second options argument
is supplied. Each call has a 4s observation budget (bridge retains its real 5s
child watchdog), each turn 60s; actual tool signal and plugin cleanup abandon the
turn. Every host/native/managed call checks the turn before admission and after
settlement. Abandonment is sticky, including through caught errors: no subsequent
filing, ACK, escalation, projection or result-persistence continuation is allowed.
Actual managed executor context, including caller identity/signal, is unchanged.

One turn is admitted, no queued turns. Unsettled promises retain slots even after
timeout; later turns/events refuse while any remain. The hard cap is four host
calls (nested managed guard observations need up to three); ordinary native RPCs
are sequential. Late resolve/reject only releases a slot; it never resumes the
abandoned handler or writes an audit result. Intent/IDs already persisted remain
uncertain for trusted exact-ID readback/operator reconciliation, never blind resend.
An already-submitted bridge transaction/managed/native operation MAY finish late;
this is not native cancellation, rollback or a guarantee of quiescence. In
particular a committed filing is not outward permission for an interrupted turn.

Startup observation is finite and leaves unresolved work pending. Cleanup stops
new typed work and aborts the supported event subscription without waiting forever
for RPC/iterator settlement; it returns unresolved count and conservative quiesced
status. Do NOT reload/create replacement adapter instances while old owned calls
remain unresolved; trusted operator readback/quiescence is required first. There
is no durable/global cross-instance in-flight RPC cancellation mechanism here.

Separate stable action rows: filing receipt, escalation, optional routine/decision
relay, status Note, overview Note. Receipt always says no approval/projection pending;
it follows journal commit and targets only the actual report lead. Unverified or
missing inputs generate NO native outward action. Duplicates return existing state
with send:false. Each send is marked uncertain and output ID persisted BEFORE call.
Fresh authorization is checked at claim and immediately before send; late successful
evidence must be reconciled by trusted exact-ID readback, never replay/relay. Revoked/old-chief/wrong-
project/source relays reject. A missing record, timeout or 409 proves no nonadmission.

Planned = durable intent only. Uncertain = attempt may have happened. Admitted =
matching Inbox/readback queue acceptance. Receipt/relay completed = that admission,
not execution/adoption/human read. Chief escalation stays admitted, not decision-
complete. Notes completed = actual exact saved ID/body list readback + watermark;
late success retains ID/old watermark and marks pending latest. UI refresh unproved.

In production, startup/events reconcile only bounded owned pending inputs/actions, never resend.
At most 4 inputs and 4 sends are inspected per pass from bounded 32-row windows;
older pending actions may require explicit operator inspection. There is no claim
that this bounded window is a complete backlog drain. New planned actions created
by recovery are not automatically sent: conservative operator reconciliation is
required. No polling daemon, goal, generic final return or automatic reconnect loop.
Stream cleanup aborts. Repeated events dedupe through durable action states; missed
events during an active operation remain pending for later event/reload/operator.

Private fixture exception: startup and event reconciliation are deliberately
disabled, even after native identity succeeds. File seals grant no recovery
authority. Every fixture bridge admission checks static/source/runtime pins and
requires actual native caller verification within the current serialized typed
turn; RPC/managed admission also rechecks pins. Discovery inventory covers only the
fixed fixture-local inputs (see FIXTURE.md), not ancestor/global effective config.
Fixture automatic recovery remains deferred to future guarded real-native
operations/controller work; pending actions must not be replayed to fill this gap.

Note creation stores intent nonce/preexisting IDs before call; actual returned ID
persists before readback. Ambiguity never permits replay, including empty lists.
An unknown ID may reconcile only by unique exact nonce/body/native origin and prior
absence; marker/title/source:agent alone is not ownership. Manual changed/missing
accepted body pauses; expected is never reset to force overwrite/recreate. Each
projection is independent. Overview uses only registered verified receipt snapshots,
warnings/waits first, omitted/missing/source-age provenance visible, <=3000 UTF16.

## Still deferred / native proof gate

First-smoke consistency details are in OPERATOR.md: host-only managed input/result
captures and bounded SQLite `smoke_state` readback join actual admissions, completed
native tool inputs/outputs, Note intent/save/list/ownership and source watermark.
This private read operation has no model tool or recovery authority. Imported JSON
can prove consistency only, never native origin; final settled cleanup is separate.

No Todo mutation, lead Plan writes, brief writes, principal-memory edits, generalized
rules/Luna evaluation, live install/binding/session/server/model/HTTP/Knowledge calls.
Exact archived message recovery has NO binding here: active context absence stays
uncertain. Long backlogs, automatic drain of recovery-planned work, full projection
refresh from chief events and robust event-stream reconnection are not claimed solved.
Chief event atomically plans separate Note actions and a fixed synthetic projection
wake to the actual desk. Wake admission is not proof that the desk runs sync. This
source checkpoint must not be rolled out before independent/native proof.

Review and real host catalog/permission/source capture proof must precede all native
execution. Then throwaway two-lead isolation/restart/rotation/adoption/rollback,
owned native Notes/scope/manual-edit/readback and actual panel refresh proof; later
one acknowledged pilot/report, rollout, day of actual use and explicit acceptance.
Source fakes are not acceptance. Q95 primary native-panel look is already approved.
