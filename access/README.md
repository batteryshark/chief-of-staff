# Central access candidate — NOT installed

One authored `model.json` supplies role capabilities, common roots, protected classes,
run classifications, rationale IDs and the small matrix. `matrix.json` is the generated
non-live result, with a drift test and model digest, NOT another policy source. Matrix expectations are
assertions, never authorization inputs to the compiler. Explicit per-assignment data
binds a role to literal POSIX roots/outputs; cwd, prose and agent names confer nothing.

Current source-only path:

```sh
python3 -B scripts/access_policy.py --matrix
python3 -B -m unittest discover -s tests -p 'test_access_policy.py'
node --test tests/access-denials.test.mjs
```

The compiler's `--binding FILE` mode emits a CANDIDATE JSON artifact to stdout. There is
no live discovery, host call or run activation. Do not use an artifact as a
production patch: `candidateOnly:true`, `installable:false`, `run.selected:null`.
The two run-profile names are classifications for the pending chief/principal choice,
not permissions or an implemented sandbox. Shell/grep/glob/execute/subagent remain
denied. The credential-tool registry is deliberately empty; no nonexistent adapter is
invented and there is no direct secret-read exception for a credential tool.

## What works in the candidate

- Eight semantic role profiles, shared research/handoff and both principal skill roots,
  explicit assigned source roots, exact typed owned writes and explicit shared outputs.
- Default deny, separate native external-directory gates, canonical external paths and
  Location-relative internal resources (including `../` within a project). Internal
  wildcard grants clamp ancestor traversal AND absolute external paths before adding
  other explicit scope grants. A read-only root must not gain writes through an internal
  wildcard. This is per-binding compilation, not a global relative `research/*` grant.
- Secret/keychain/native-auth/env guards follow all allows. Explicit narrower custom
  denials are retained as constraints. Whole-home/ancestor bindings, unspecified scopes,
  unknown roles and invalid output roots refuse. Credential path classes are an initial
  candidate, NOT a discovered complete inventory of every credential store.
- Pure custom-agent JSON/standard native YAML emission preserves body bytes and other
  metadata. Complex YAML refuses rather than guessing. Caller must use compile_for_agent
  to retain stricter denials, including blanket action denials. Only EXPLICITLY identified
  managed baseline rules may be retired as a migration input; an unknown user blanket
  deny is not silently removed because it resembles the central default.
- Per-rule provenance IDs/reasons, model/binding digests and no secret/environment value
  in a model input. Native triples contain only supported action/resource/effect fields.

`denials.mjs` is a pure observation/redaction/review adapter, with NO hook registration,
file append or model execution. `denial-log.mjs` is a private owned-root JSONL sink candidate,
proved only in the unique native fixture; no global logger is installed. Single-process
append is serialized; exact session/message/call correlation suppresses serialized-fallback
duplicates even when action/rule fields were lost. The first observation is retained, not
silently upgraded or replayed. Concurrent independent processes are not coordinated.
It uses only structured denial types, not message-text
parsing. Exact native rule lists can be matched to generated IDs; absent/stripped/
unmapped/malformed native evidence remains UNKNOWN, not replayed model judgment.
Path tails are redacted unless the exact path was explicitly reviewed as public; syntax
or entropy checks alone cannot prove a filename contains no credential. Unknown roots,
raw commands/env/error text and raw rule patterns are not serialized. Role attribution requires exact session+agent binding; reviews are DATA,
require a central rationale/regression and cannot grant or retry.

Reporting is part of the same policy: exact chief-post origin/session/directory plus
fresh chief pointer and tool-visibility candidate, OR a declared own chief-inbox output;
workers retain exact parent-return correlation, not arbitrary direct chief/session sends.
Actual bus enrollment, context filters, parent-return correlation and native tool presence
are unverified until their fixture proof. Existing dispatcher context currently removes
all tools except heartbeat_resolve; generated read permission is NOT actual read visibility.
Galley retains ownership of its writer launcher; the kit supplies no live writer
enrollment or private session-migration record.

## Honest boundaries / still missing

The matrix and native-shaped observation tests are NOT native-host evidence.
Native deny observations may expose rules, omit matching rules or lose action/rule
metadata during serialization. Ordinary rejection may have no execute.after callback
and only an aborted stored result. Correlated asked/replied events are required for
that branch, not a guess that every abort is a deny. Public tests use a synthetic
native-shaped event envelope; private probe receipts are not distributed.
No generic event subscriber/rejection service is installed. This is NOT all-agent/non-tool
coverage, OS read tracing or normal role migration. No claim that every credential class,
custom adapter or arbitrary agent denial is covered. Generic serialized errors may lack
action as well as rule; both stay unknown. No global logger is installed.

Lexical normalization is NOT symlink/process isolation. General shell/project test code
can use host files/environment/keychain without native read checks. Native grep does not
enforce every matched file's read rule. Neither named run profile is selected or activated;
no exception, universal secret guarantee or deadline change is inferred while the genuine
chief/principal decision is pending. This source candidate changes no installed
read-only native API/access effects and supplies no private archive as authority.

Future live installer must validate existing real roots/symlinks, migrate only explicit
role/session bindings, prove custom legacy scope differences, preserve stricter user
constraints and coordinate active work. Old session rules override agent changes; the
candidate does not mutate them. Unsupported headers/unknown bindings are a stop, not
permission to reconstruct prompts or broaden grants. Role cores are not included by
this access candidate; separate authorized prompt-only maintenance has its own receipt.

## Non-live installer integration

`scripts/install-access-policy.py dry-run --manifest FILE --output NEW_DIRECTORY` imports
the SAME central compiler/matrix and emits permission-only `.agent.md` candidates, policy
and all-role visibility/communication sidecars plus a create-only before-hash receipt.
There are no native calls or installed writes. Explicit agentRoot/roleFile/binding inputs,
expected source SHA256 and managed-baseline classifications are required; no discovery
or inferred assignment. Custom ask constraints currently REFUSE migration instead of
silently widening. Custom denies, metadata and prompt body bytes are preserved. Conflicting
reporting constraints refuse; workers keep parent return, not broad session-send grants.

Existing assigned roots must be canonical real directories; all existing components of
source/output/common paths must be non-symlinks. Explicit future output/common roots may
remain missing and are recorded, not created, dropped or used to infer broader roots.
Source hashes and path identities are checked again before receipt publication and by
`verify --output DIRECTORY`. Candidate bundles must be new and outside watched `.opencode`
and bound installed agent roots. Private0700 bundle/read-only0400 files plus hashes and
exclusive create are API-level immutability, not an OS protection from their owner or CAS.

`activate --output DIRECTORY` ALWAYS refuses; every compiled run.selected remains null.
No trusted-host default, global logger, context filter, known-session override or live
render/installer route is activated. Visibility sidecars are integration inputs, not tool
presence proof. Tests construct inert synthetic eight-role bindings and temporary
receipts; no private installation summary or operational readiness record is shipped.

## Passive observer candidate (22 Oct continuation)

`observer.mjs` composes the proved native `execute.before` / `execute.after` hooks and
public `permission.asked` / `permission.replied` stream. It is disabled by default,
unregistered and uninstalled. The enabled candidate requires an exact Location and
explicit session/agent/compiler bindings. The installer emits only disabled
`observers.json` sidecars; it cannot activate them. One future sink owner must be
chosen explicitly: independent processes do not coordinate appends or deduplication.

Before hooks retain call identity only, never input/env/commands. Exact asked/replied
correlation records ordinary rejection even without execute.after. Arbitrary `aborted`
errors are not denial evidence. Non-tool or missing-call native rejection stays unknown
for role/rule/path where unbound. The global stream admits only exact event Location or
an already observed local native call. Pending maps cap at256 each; eviction, append
failure and stream loss are counted without retry or permission changes. No permission
assert/reply, prompts, timers or grants exist. Cleanup disposes hooks/aborts the stream.

Sink dedup now keys exact session/message/call without tool label, which may be unknown
on the native-event fallback. First observation still wins, including incomplete metadata;
no later enrichment or complete-rule-attribution claim. Source tests replay a synthetic
native-shaped rejection envelope; this is NOT native deployment/coverage proof.
No global/non-tool universal coverage, past-event recovery or arbitrary same-UID isolation.

Storage-failure safety: a failed rejection append retains its sanitized correlation in
the existing bounded maps; only a separately delivered event can attempt logging again.
No retry timer/queue is created. Observer status reports `loggingAvailable:false` on
failure. The sink parks after any append/fsync exception, because bytes may already
exist: queued/subsequent appends reject before writing or claiming a duplicate. Its
status reports `available:false`, `write-uncertain-inspection-required`. Initialization
stat/read/parse errors close the opened descriptor while preserving the original error.
Parking lasts for that sink instance, not across processes/restarts; inspect retained
bytes before deliberate reopen. No automatic truncation, repair, durability claim or
cross-process recovery is supplied. Correlation can still expire by bounded eviction
or cleanup. These behaviors have source fault-injection tests, not live disk-fault proof.

## Independent review corrections and explicit remaining failure

Final emitted rules now receive per-binding acceptance checks, including required shared/
assigned reads, explicit writes, protected paths, outside access and transport prerequisites.
Chief-inbox requires both fresh-pointer read and exact output edit, with their native
external-directory gates. Conflicting custom denials refuse; they are never removed.
`*.acceptance.json` is separate from the176-case synthetic structural matrix. Both are
lexical source checks; optional explicit session snapshots are described below. Native
visibility and live session ownership/freshness remain unverified.

Retained file rules normalize `$HOME/` and `~/` as native loading does; shell rules do
not. Indentless/duplicate permissions YAML refuses instead of corrupting frontmatter.
A changed generated prefix with recognizable clamps now requires explicit prior-generation
classification/provenance rather than reclassifying old baseline denies as user clamps.
Receipt-anchored automatic upgrade is still unimplemented; exact same-model regeneration
and explicit baseline migration remain supported. Unrelated metadata/body bytes survive.

**Production file-identity protection is BLOCKED.** On this volume `.env` and `.ENV` can
name the same file while native-shaped lexical matching allows the latter. The model,
compiled candidates, per-binding acceptance and receipts explicitly carry
`blocked-native-canonical-identity-unproved` / `productionReady:false`. No Python casefold
or enumerated-case illusion was added. The independent required-deny assertion is retained
at `tests/integration/access-case-alias-pending.py`; it intentionally still fails here.
Until authorized native canonical-identity enforcement is proved, neither a green lexical
matrix nor a selected host-run exception can establish protected-file coverage.

## Optional role + session snapshot acceptance

Each dry-run manifest role may include `sessionPolicySnapshot` with exactly:
`sessionID`, `agentID`, `directory`, `rules`, `rulesDigest`. `rules` is the ordered native
action/resource/effect list (allow/deny/ask); `rulesDigest` is `access_policy.digest(rules)`
(SHA256 of sorted-key compact JSON). Session and directory must match the explicit
reporting origin/Location; when observerIdentity is also supplied its agent/session
must match. This is caller-declared offline input, never a native lookup or mutation.

`compose_session_policy` appends normalized session rules AFTER all role/custom rules.
Last matching rule wins, including external-directory gates. It preserves every rule's
order and the raw snapshot; `session-override-N`, `layer:session` and snapshot index
identify provenance. Actual per-binding acceptance uses this composed policy, so a
stale blanket read deny fails required reads and stale secret allows fail forbidden
access checks. Literal session file grants additionally check previously denied paths
that generic matrix probes might miss. This finite lexical matrix is not an exhaustive
proof over arbitrary wildcard intersections or native filesystem identities.

On conflict no bundle is published and no rules are removed. On success the separate
`<binding>.effective-policy.json` retains the raw snapshot and effective ordered rules;
the `.agent.md`/`.policy.json` remain role-only. Acceptance identifies the snapshot and
winning layer/rule, receipts bind its digest, and any disabled observer sidecar receives
the effective manifest. Snapshot absence remains explicitly `sessionOverrides:not-evaluated`;
an explicitly supplied empty list is distinct. Identity/freshness are always unverified.
`installable:false`, the case-identity gate, and `run.selected:null` remain unchanged.
