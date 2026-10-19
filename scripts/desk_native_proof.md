# Staged native proof protocol — DO NOT EXECUTE in the source lane

`desk_native_proof.mjs` exports a bounded exact-record observer, not a standalone
driver, installed plugin or permission to run native tools. It accepts only an
existing supported host ctx and a fixed reviewed manifest. It discovers no server
or auth and creates nothing. All scripts in this lane remain unexecuted natively.

Before execution, independent source review must approve the exact pin, optional
role installation/catalog/executor checks and a separate fixed owned-effect manifest.
Supply only new throwaway scope/session/Note IDs, never the removable Q95 fixture
or Example pairing. The owning harness must capture real tool invocation context;
do not manufacture c.sessionID/c.agent/c.messageID/c.id or call tools as another
session to make a green trace. This phase supplies NO such privileged invocation
driver and makes no claim that source fixtures are native acceptance.

Use a <=240s whole-run watchdog, <=4s native OBSERVATION/<=5s Python children, sequential
jobs and exact-owned cleanup only. Observe tools/catalogs and actual queue/tool
records, not model claims. Keep credentials/private URLs out of evidence.

The shared observer boundary has a 60s observation deadline and actual caller
abort fencing. Unary session RPCs cannot be cancelled by passing RequestOptions.
Timed-out RPCs may finish late: the observer retains unresolved slots per ctx,
rejects another observation until settlement, and never continues to another read
from the abandoned observation. Its supported event subscription is aborted, not
awaited indefinitely; no underlying-RPC quiescence is claimed. Do not replace the
ctx/adapter to bypass the cap. Operator exact-ID readback remains required before
replacement/restart or declaring the owned fixture quiescent.

Required native cases, each with expected effects and owned IDs before sends:

1. Two registered leads interleave report inputs and assistant finals. Exact host
   ledger, actual input/tool IDs and deterministic outbound synthetic IDs must
   correlate separately. Final prose never returns as reporting receipt. Each
   receipt follows durable filing; reserved reports separately reach current chief.
2. Foreign user/synthetic metadata, arbitrary caller labels/proof bool, wrong
   native agent/project/location/epoch, moved/revoked sender, missing/compacted
   readback: no verification/outgoing receipt/chief spam. All generic tools absent
   from desk catalog AND denied at direct executor calls. Test replaced managed tool.
3. Deliberate loss before/after admission and before result persistence; close/reload
   adapter. Exact owned IDs/body/target readback may establish admission, never idle,
   timeout/409 or empty search. No blind resend. Missing records stay uncertain.
4. Current-chief event versus old chief/wrong project/source/revision/revocation
   races. No quoted principal signoff. Relay and projection wake have independent
   action IDs. Native wake reaches idle without a goal; no ACK ping-pong/digest spam.
5. Exact native project namespace versus canonical-directory collision before create.
   One owned Note/status and one home overview. Actual returned ID saved before
   list readback, actual accepted body becomes next expected. Trim/UTF16/escape
   bounds, manual edit/delete, partial failure, late watermark/ID, ambiguous create
   unique nonce/origin and empty-list no-replay. Never mutate Todo/lead Plan/brief.
6. Running-lead contract acknowledgement + delivered report/receipt, fresh lead,
   desk rotation AND chief rotation, revoked late events, then actual restored-route
   acknowledgement/report for rollback. Preserve all uncertain IDs and journal.
7. Actual principal panel refresh observation separate from native save/list proof.
   Q95 first-look approval is already complete, not a new taste gate.

Observer manifest v1: `authorization:separately-authorized-throwaway-proof`, at most
5 sessions, each exact sessionID/agent/projectID/canonical directory; <=16 exact
inputs `{id,type,text}` and <=16 actual calls `{messageID,id,name}` per session.
Use native admission/ledger bytes, not proposed/echoed model data. Output contains
IDs/match/status only; no private body echoes. Observer is a single snapshot, not a
poll/replay engine. A later authorized driver must collect complete transitions,
actual native catalog/denial evidence, stored Note scopes and panel evidence.

Stop after two unsupported native approaches and ask. After accepted native proof,
Luna evaluation remains separate; then one real acknowledged pilot/report, rollout,
day of actual use and explicit acceptance. This source lane completes none of those.
