# Voicestack call adapters

## Ordinary deployed call: chief_urgent_call

`ordinary-call.mjs` exposes a SEPARATE tool only with explicit code-owned binding.
Its default export is inert. It executes the reviewed owner CLI with fixed argv:
`node bridge/reachout.mjs send --kind urgent-call --reason decision|goal-risk
--session NATIVE_CHIEF --id UUID --title TEXT --body TEXT --message-id NATIVE_MESSAGE`.
No shell, inherited environment, model-selected path/identity/destination, socket
shortcut, credential read, reusable grant, owner issuance or service restart.

Authority: principal.md 22Oct standing chief call permission (no per-call yes),
fresh existing chief.json, exact native session/agent/Location/message context and
native permission.assert on `chief_urgent_call` / `ordinary-urgent-call`. No permission
rule is added. Binding config names canonical code root, absolute Node executable,
reviewed CLI hash, existing chief pointer, approved agent/Location and a private
attempt directory. CLI drift refuses before execution. Config is trusted owner code,
NOT an authenticated grant. Same-UID processes can forge CLI session arguments;
the ordinary sender does not provide cryptographic per-caller isolation.

Actual deployed contract pinned to `a181b63f188082e7c285d3fb119f22245b366b43`:
private checkout-anchored 0700 directory/0600 sender socket, current-chief validation
before and after native session/message lookup, maintenance holds, paired device,
bridge Calls switch, no-VoIP/outstanding-call refusal, durable intent and same-ID
coalescing/conflict rejection. Phone owns quiet hours/Calls/Focus. Ordinary daily and
spacing caps were removed; stale CONFIG constants do not imply active ordinary caps.
The owner CLI retains guarded speech preparation (up to150s) before socket send,15s
socket deadline and15s first-phone-receipt observation. Its final status read can take
another15s. The adapter has one200s outer budget, not a15s end-to-end promise. Killing
the CLI does not prove child preparation or backend cancellation. No automatic retry.

One create-only private UUID attempt file is fsynced before CLI launch; it holds
identity/digest, never title/body. All reuse refuses, including unknown outcomes or
restart. Failed persistence refuses before CLI; an ambiguous marker is not deleted.
This is a no-replay fence, not a second call-status ledger. Read status through the
owner's existing explicit read-only route; never generate another ID to retry unknown.

Results contain only allowlisted delivery/policy/phone-receipt enums and optional
validated quiet-hours time. Raw stdout/stderr/errors/help/text are never returned.
The real CLI writes its phone receipt to stderr even on success; that stream is
bounded and discarded. `recorded` means backend record evidence, not ringing;
`phoneReceipt` comes from the CLI's separately observed first receipt. Media remains
not-proven. Malformed, wrong-ID, cancelled, oversized or ambiguous output is unknown.

Portable `tests/ordinary-call.test.mjs` uses synthetic child scripts and caller/permission
spies. Explicit source integration imports actual pinned CLI/policy/backend and injects
fake speech/APNs/native-origin interfaces: no real socket, credential, warm or phone call.

### Existing-entry maintenance

`./install.sh --ordinary-call-maintenance /absolute/chief --revision NAME --dry-run`
preflights an already installed, exact receipt-owned entry. Omit `--dry-run` only
in a coordinated chief-Location window: the atomic watched-entry replacement may
reload that Location. It does not explicitly reload/restart or invoke a call.
The reviewed `atLeast` helper retains its2.0.32 minimum; malformed, prerelease and
older versions refuse registration. The bound runtime, CLI hash, current pointer,
permissions, roles and private attempt directory are not rewritten. Unknown or
modified ownership/dependencies refuse; each revision has a no-overwrite backup.
There is no fresh enrollment or managed-call activation path. Registration proof
must use current native registry/receipt reads, NEVER `chief_urgent_call` execution.

## Managed call adapter — deferred and production-unbound

Owner correction, 22 Oct 2026: `managed-call-v1` was **never deployed**. Its reviewed
source exists only on deferred `recipient-registration-oct22` at
`866cc313166854e93ce5838e39805d726f290903`. Earlier source fixture success proves
that deferred contract only; it does not establish deployed tool availability.

Deployed main `a181b63f188082e7c285d3fb119f22245b366b43` supports ordinary
`send --kind urgent-call`, reasons `decision`/`goal-risk`; messages use Nod.
It has no managed-call modules. No combined merge is planned by the owner.

The default plugin and even path/resolver-bound factories now remain inert unless
explicitly composed with `fixtureOnly:true` for offline tests. There is no production
activation path. This flag is owner-code fixture intent, not a sandbox or authority
proof. Do not install a fixture composition. No fallback to ordinary CLI is supplied:
that substitution would shed the managed recipient/caller guarantees.

`tests/integration/call-tool-source.test.mjs` pins the deferred branch exactly and
uses synthetic grants, private scratch and a trap backend; it retains that branch's
`dev-override.mjs` dependency. `voicestack-calls-only-source.test.mjs` independently
checks the deployed main schema offline. Neither sends a live call.

## Retained front-door constraints

The ordinary chief-only tool above uses the existing deployed route. Managed calling
remains unavailable; it is not a fallback implementation of that stronger contract.
Historical technical-chief-pointer/warm/push scripts are not approved cold-wake,
background-readiness or ring contracts. Never invent availability from prose.
The principal-facing chief may invoke an actually exposed authorized call tool
directly; Ops is not a mandatory per-call intermediary. The owner must supply exact
exposure/backend, authorization and observed-outcome contracts. Shaping is not
implementation authority. Preserve opt-in/revocation, Focus/quiet and resource guards.
No live call, cold wake, background, ring or microphone test without a genuinely
agreed future window. Requested, executing, rang, connected and failed remain distinct;
unobserved stages stay UNKNOWN. Dispatch/ACK/install is not contact, and uncertain
delivery is not retry authority. Do not duplicate Fleet adoption, modify the bridge,
impersonate a caller or issue new live grants. Only the explicitly described offline
source fixtures above may use synthetic private CLI/socket transport.
