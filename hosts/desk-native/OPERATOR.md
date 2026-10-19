# First-smoke operator kit — SOURCE ONLY

This is a staged, manual managed-tool workflow, **not permission to execute it**.
Independent source review, a concrete non-Claude model/cost choice and separate
native authorization are gates. No live fixture was staged or activated by this lane.
Q95's removable project, Example bindings, credentials, goals and global settings
are not inputs. Knowledge is primary; Canvas is not needed for this smoke.

## Offline preparation commands

Run from the project root. `F` must be a NEW EMPTY canonical private directory outside
Git. `GENERATED` is the operator's exact ALREADY-generated managed package source,
ending `/agent-tool/openchamber-agent-tool/index.js`; never a credential, env dump,
model-provided path or newly generated substitute. If absent, STOP; do not bootstrap
another server, extract callback auth, fetch a package or reuse Example pairing.

```sh
node --check hosts/desk-native/fixture-operator.mjs
node --check hosts/desk-native/fixture-observer.mjs
node --check hosts/desk-native/fixture-evidence.mjs
# F, PYTHON and GENERATED are explicit operator-selected absolute canonical paths.
node hosts/desk-native/fixture-operator.mjs stage-inert "$F" "$PYTHON" "$GENERATED"
node hosts/desk-native/fixture-operator.mjs steps "$F" "$MODEL"
```

`stage-inert` preflights all source inputs before writes, refuses any existing root
content and writes ONLY private offline files. Its native config has enabled=false;
no native/model/SDK/HTTP operation is imported or invoked. `fixture-assets.mjs` is the
exact source allowlist, including every new helper and fixed config builder. Review
the generated inventory externally; its hashes/ownership nonce are NOT identity.
No helper is a model tool. The inert optional installer copies these modules too,
without a discoverable root entry/config or activation.

## Future authorization phase A — fixed definitions before FIRST load

This phase is NOT part of the <=120s smoke. Trusted operator checks ancestor/global/
managed/explicit config and later overriding plugins cannot weaken these guards;
fixture-local discovery is separately checked by the entry. Do not read/change
global settings to get this proof. If that precondition cannot be established, STOP.

Before any session/location load, review the exact four `pendingConfig(F,PYTHON)`
definitions and package. The sole pre-load delta is `plugins[0].options.enabled=true`.
The following is an exact FUTURE operator terminal step, **not run by this lane**:

```sh
node --input-type=module - "$F" "$PYTHON" <<'JS'
import fs from 'node:fs';
import {pendingConfig} from './hosts/desk-native/fixture-config.mjs';
import {privateFile,privateRoot} from './hosts/desk-native/fixture-operator.mjs';
const [F,python]=process.argv.slice(2),p=F+'/.opencode/opencode.json';
privateRoot(F);privateFile(p);
const expected=pendingConfig(F,python);
if(fs.readFileSync(p,'utf8')!==JSON.stringify(expected)) throw Error('not untouched inert config');
expected.plugins[0].options.enabled=true;
fs.writeFileSync(p,JSON.stringify(expected),{mode:0o600});
JS
```

Definitions then NEVER change. No reload, replacement entry, enrollment/admin tool,
new RPC or new service is used. No model-writable file grants authority.

`steps F MODEL` emits four exact existing managed `session.create` payloads:
`{directory:F/home,agent:proof-desk|proof-chief,model:MODEL,title:...}` and
`{directory:F/lead-a|lead-b,agent:proof-lead-a|proof-lead-b,model:MODEL,title:...}`.
The model must be concrete, approved and non-Claude. Omit prompt, goal, worktree,
returnResult and delegation. Desk/chief share home; lead B remains idle. At most
four sessions; never create a replacement after uncertainty.

Before EACH admission, retain its exact planned payload and `uncertain` in the
private operator admission journal. Immediately persist its ACTUAL returned ID,
agent/model/directory/result before the next call. Missing ID/partial/error means
STOP with uncertainty; do not repeat create. These four new IDs, not title searches
or guessed UUIDs, select all later observations. No previous fixture is adopted.

Use the same existing managed tools, individually, once:

```json
{"action":"session.list","parameters":{"directory":"<exact F/home or lead-a or lead-b>","withStatus":true,"limit":8}}
{"action":"session.status","parameters":{"directory":"<actual directory>","sessionId":"<actual returned ID>"}}
{"action":"knowledge.list","parameters":{"directory":"<exact F/home or lead-a or lead-b>"}}
```

Status's top-level directory is request scope, NOT authoritative location. Native
Session.Info from list supplies `id,agent,projectID,location.directory,model.providerID,
model.id,time`; require status.type=idle, unarchived, exact agent/path/current model.
Managed Knowledge's returned `projectId` is separate. It must be distinct for all
three canonical scopes; Core projectID may legitimately be the SAME global ID.
Never infer either ID from basename, request directory or enrollment metadata.
The installed source anchor is `openchamber-control/service.js:860–910`: list
passes through actual Core session records and overlays status, whereas status
alone returns only sessionId/request-directory/sessionStatus. Missing fields STOP.

## Descriptor bootstrap, including late arrival

Entry uses supported `ctx.tool.transform`, `ctx.tool.list` and the existing
context/generate/compaction request hooks. It records bounded descriptor hashes,
sanitized JSON schema, enabled/codemode flags and the already-generated source hash
to private `evidence/metadata-{home,lead-a,lead-b}.json`. No descriptions, executor,
raw env/options/auth text or secrets are exported. This is allowed METADATA ONLY
while pending: no Session.get, bridge, store, managed call or projection occurs.
All three locations must yield the SAME managed descriptor/source pin. Read/write
descriptors must also be supported at actual guard time; aliases/unknown shapes STOP.

If the descriptor is absent, the entry stays pending. If native registration needs
one real preparatory catalog/typed turn, only AFTER separate authorization send one
owned lead turn with `desk_report({report:<benignReport(observed)>})`, and one home
desk turn with `desk_inbox({inputId:"pending-metadata-only"})`, only in locations
still missing metadata. Expected result: missing runtime binding refusal BEFORE
native get/bridge/store/managed/projection; only metadata snapshot is possible.
Use at most one preparatory turn/location, no blind resend and no invented event.
Lead B may need that preparatory turn but remains idle during first smoke. These
preparatory refusals are NOT permission proof or successful native filing. If an
actual descriptor still does not appear, STOP pending on that exact supported hook;
never invent tool IDs, schemas, RPC, source pins or an execute-as-session context.

## Future phase B — trusted collector and runtime writer

Save every actual tool result verbatim in private F/evidence. For each scoped list
or Knowledge observation, use this documentary wrapper (the request is the exact
sent payload, response is the actual returned schemaVersion/ok/action/data envelope):

```json
{"request":{"action":"session.list","parameters":{"directory":"<exact scope>","withStatus":true,"limit":8}},"response":{"schemaVersion":1,"ok":true,"action":"session.list","data":{"sessions":["<actual native records, not this placeholder>"]}}}
```

Knowledge uses `action:knowledge.list`, the exact scoped request and actual listing
under response.data. Hash the SAVED bytes, not re-encoded prose. Collector verifies
each response hash/request scope/actual returned fields against normalization. It
does NOT authenticate native identity from JSON: a trusted operator could forge a
file; native get, active input and managed readback STILL gate every real effect.

Prepare one private JSON file with EXACT top-level keys:

- `origin:"trusted-operator-saved-managed-responses"`, `quiescent:true`,
  `expectedEpoch:1`, concrete `model`, `observed` (fixed ISO run timestamp).
- `sessions`: EXACT four records, each with `id,agent,projectID,location:{directory},
  time,model,status:"idle",disabled:false,goalActive:false,response_file,response_sha256`.
  model is normalized `providerID/id`; time contains only numeric created/updated/
  archived fields and must match the saved native time object EXACTLY (keys and
  values). Omission is allowed only when the underlying source omits that same
  field; never invent time or drop updated. `response_file` names an exact F/evidence file above. Validate
  disabled/goal state from reviewed fixed definitions, own promptless/no-goal create
  receipts and actual status; if unknown, do NOT fill false. Preserve all create and
  status evidence separately in the admission journal. Never claim the normalized
  fields were all literal fields of Session.Info.
- `knowledge`: EXACT home/lead-a/lead-b records with `directory,projectId,
  disabled:false,response_file,response_sha256`. Do not add request-scope aliases.
- `rule`: the exact independently reviewed single benign rule below.

Prepare the fixed report/rule, with expiry at most 120s in the future, immediately
before binding (after metadata/session preparation). `OBSERVED` is the SAME fixed
ISO timestamp in the input. The trusted Strong/operator approves only THIS hash,
recipient and expiry, not fixture-chief approval or broad technical delegation:

```sh
node hosts/desk-native/fixture-operator.mjs rule "$OBSERVED" "$ACTUAL_LEAD_A_ID" "$EXPIRES"
node hosts/desk-native/fixture-operator.mjs bind "$F" "$PRIVATE_OBSERVATIONS_JSON"
```

The only report is project lead-a / id first-smoke / revision 1 / state active /
landed `Owned fixture report filed.` / next `Stop after first smoke.` / your_part null /
request ack / rule fixture-first-smoke / fixed observed. Its full canonical JSON
SHA256, recipient, epoch=1, active state and expiry are checked in JS and rechecked
by NativeStore classification. ACK text is `Filed. No approval implied.` This rule
only suppresses chief escalation for that one report; it does NOT send a second
routine relay. The single universal synthetic filing receipt remains unchanged.
Mutation/expiry/revocation refuses or escalates within throwaway scopes, never
rewrites a rule to match model prose. Empty ordinary rules still escalate.

Bind preflights EVERY destination and input, config/source pins, counts, duplicates,
current model, exact roles/locations and namespaces before ANY runtime mutation.
It is exclusively absent-create with a retained uncertain binding-attempt marker;
partial failure is NOT retriable. It writes COMPLETE native-host/registry/routes,
desk/chief pointers and the final binding-manifest LAST. No definitions/config are
changed or reloaded. All sessions must be quiescent and ingress stopped while binding.
The first guarded call seals exact bytes separately per loaded location; every
bridge admission still requires the current actual native caller and pin checks.

## Future phase C — ONE <=120s smoke

The bind command emits the exact existing `session.send` payload to ACTUAL lead A:
one prompt requesting the registered `desk_report` with the exact report object.
There is no script control fetch. Preserve the send's planned/uncertain admission
before calling it once. Missing/noop/idle/model-final-only is unknown STOP, not retry.
Native prompt carries the exact host-minted input to desk; the fixed desk agent must
call registered `desk_inbox` with that inputId. No raw final watcher or free-form reply
has authority. Do NOT manually re-send an already-admitted desk input. If a turn
fails to use its tool, STOP with exact retained IDs; never make a green receipt by hand.

START is before the first bound registered native get, AFTER all preparation.
The root-wide watchdog is 120s, each unary RPC observation <=4s, each turn <=60s,
bridge retains its 5s child watchdog, <=16 captured contexts/location and <=128
owned evidence records/root (also byte bounded). Event subscriptions are abortable;
there is no sleep/poll loop, goal or service. R1 held-slot/late-result fences remain.

After actual native caller verification, a HOST-ONLY closure probes actual registered
generic read/write/managed executors using unchanged actual c and fixed args:
`read({path:F/owned-empty-canary,offset:1,limit:1})`,
`write({path:F/owned-empty-canary,content:""})`, and
`openchamber_knowledge({action:"knowledge.list",parameters:{directory:<own location>}})`.
Canary must remain empty/owned/private/single-link/nonlinked. Denial requires a
private out-of-band entry receipt from the actual generic executor guard, matched
to exact tool/args/caller; neither error prose, missing catalog nor model claims pass.
Unexpected allow/unknown shape/name stops the WHOLE root before privilege; an
unexpected write can affect ONLY that owned empty canary. No shell or arbitrary
probe argument exists. Managed sync uses the unchanged one-use private host ticket;
the generated executor retains callback auth internally, never extracted/reused.

Knowledge's supported installed generator schema requires ONLY `action`; explicit
`parameters` is optional and supported. The fixed own-directory list validates its
action against unique `oneOf.const` branches and the explicit directory property.
Unknown constraints, aliases or action sets STOP, not a general schema interpreter.
This static source compatibility is not a captured native descriptor claim.

The host captures exact registered tools, native get/active contexts, durable bridge
input/action/receipt/Note transitions and pinned catalog/denial evidence privately.
Execution events trigger bounded read-only native snapshots ONLY for verified owned
sessions; fixture event reconciliation/bridge replay remains disabled. Missing or
busy-interleaved snapshots remain unknown. The pure validator correlates report ->
persisted input -> exact desk active input/tool -> durable filing -> ONE receipt to
exact lead -> one status Note plus home overview. Returned actual Note ID persists
before list readback; action IDs and source watermarks must match. Real get/model/
project/location, message/call/input/output IDs and completed native tool parts are
required. Compaction, missing records, model final, idle or admission alone cannot pass.

Host-private evidence includes actual managed `knowledge.list/save` parameters,
unchanged caller IDs and decoded successful results. After filing/projection it also
reads `smoke_state` through the closed private bridge: one persisted input, exactly
three action rows, two Note ownership rows, the sole verified source event, and
the source snapshot/generation watermark (exactly 1 for this isolated first smoke).
This is a bounded readback, not a model tool, recovery path or canary-control API.
The validator joins unique prepare/claim/prompt/admission/input/file transitions,
registered/native completed tool INPUT and exact OUTPUT, current identity and send
recipient; Note intent/proposed body/nonce/scope, actual save/returned ID before
list, exact list item/native origin, source watermark and completed durable rows.
Omissions, duplicates, contradictory matching summaries and wrong ordering STOP.
Root correlation can stop ingress only after that complete chain; the separate
final validator still requires settled `cleanup-final.json`.

```sh
node hosts/desk-native/fixture-operator.mjs validate-evidence "$F"
```

This validates correlation, NOT authenticity of arbitrary imported JSON. The actual
host writes evidence; offline FAKE fixtures only prove source contracts. A correlated
result is first-smoke only: not human UI refresh, whole matrix, cheaper judgment,
pilot/adoption/rollout or a day of actual use/acceptance.

## Stop / retained IDs / guarded fixture-only rollback

Host stops ingress and aborts all root subscriptions/fences on a correlated chain,
guard failure, event cap or watchdog. Process root tombstones refuse replacements.
Cleanup clears actual-context references and records unresolved/quiesced honestly in
`evidence/cleanup.json`; unary native work may still finish late. No native cancellation
or quiescence is inferred. Native session/turn termination uses ONLY separately
authorized exact owned IDs via existing host UI/tools, never a new control RPC.

If unknown/unresolved: retain F, binding-attempt, admissions, exact four session IDs,
input/output/call/action IDs, Note IDs/bodies/nonces/receipts and all source pins.
Do not resend, reload, rotate, delete/recreate, overwrite sealed routes, clean up
unknown Notes or claim success. Inspect exact native readbacks and status once after
ingress stops; escalate remaining uncertainty to the operator, not a permissive rule.

Rollback is fixture-only and quiescence-gated: verify F's ownership/source/config
pins, expected epoch=1 and exact session IDs against the final binding manifest;
stop only those owned turns, preserving any unresolved IDs. After independent exact
readback proves every call settled, retain ledgers; any separately authorized Note
removal must match the persisted Note ID, canonical managed scope, exact last accepted
body AND native origin/nonce, and recheck immediately before deletion. Changed,
missing, ambiguous, foreign or manually edited objects are retained. Never restore
whole files/global settings, delete principal data or repoint live routes to make a
rollback look green. This kit intentionally has no automatic destructive rollback
or native delete/interrupt driver. Retaining a fenced fixture is the safe default.
