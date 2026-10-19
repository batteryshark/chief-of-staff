# Private native fixture — staged operator kit, SOURCE ONLY

**The executable source/operator sequence is [OPERATOR.md](OPERATOR.md).** It
supersedes the original missing-driver checklist below; those paragraphs describe
the 3b31978 baseline, NOT the current implementation inventory. The historical
protocol is retained for its identity/uncertainty requirements, not as a second
activation path. Current collector, descriptor bootstrap, canary and evidence
helpers are implemented and tested offline, never proven native by fakes.

Source only. No activation, session, model, HTTP, settings, credential or Knowledge
operation is authorized by this document. Fake tests are not native proof.

## Fixed definitions; pending runtime binding

`fixture-package.json` is the exact private package descriptor to copy as
`F/fixture-plugin/package.json`. The package contains the full relative
`hosts/desk-native` and `scripts` trees, not just the entry file. Its default export
is `{id,setup}`; the installed loader passes options as `ctx.options`, location as
`ctx.location.directory`. `pendingConfig(F,python)` is a pure inert config builder:
four exact primary agent descriptors and deny-first permissions, disabled default.
The optional installer stages these assets in `home/desk/native-runtime` WITHOUT
a root package.json, discoverable entry/config, F creation or activation.

Before a separately authorized FIRST location load, the operator must stage the
complete private package at `F/fixture-plugin`, review/pin its hashes, and stage
`F/.opencode/opencode.json` from the builder with enabled=true. F and the exact
home, lead-a, lead-b, fixture-plugin children must be outside existing Git roots;
all fixture directories 0700/files 0600, owned, regular, nonlinked; source files
single-link. No production scope or Q95 fixture is admitted. Source inventory
`fixture-source.json` maps exactly the relative runtime assets listed in
   `fixture-assets.mjs` to reviewed sha256 values. The inventory is not self-authenticating
authority; an operator/reviewer must approve it before native loading.

Fixture-local discovery allowlist: only F/.opencode/opencode.json is admitted.
At F and each of home, lead-a, lead-b, fixture-plugin, preflight and every later
check reject direct opencode.json/opencode.jsonc, alternate .opencode JSON/JSONC,
and .opencode agent/agents/mode/modes/plugin/plugins/command/commands/skill/skills
containers (even empty or linked). .agents and .claude compatibility layers are
also refused wholesale. The expected F config remains exactly byte-pinned. An
optional otherwise-empty .opencode container must be private/nonlinked before
checking children; absent paths appearing later refuse too. Unexpected links are
never followed. Ordinary runtime, logs, stores and evidence outside these discovery
inputs are allowed; this is not a whole-directory content inventory.

Names are grounded in the installed CLI text: eR at 120709554 lists JSON/JSONC;
ConfigDiscovery.discover walks all ancestors and loads .opencode layers after direct
documents. ConfigAgentPlugin (120957847+) scans {agent,agents}/**/*.md and
{mode,modes}/*.md including links; PluginSourceDirectory (120953045+) discovers
plugin/plugins JS/TS or package directories, including linked entries. Installed
ConfigCommandPlugin and ConfigSkillPlugin also scan command/commands and skill/skills.
This finite local inventory is NOT the entire effective loaded configuration.
Trusted operator must separately ensure ancestor layers above F, global/system and
managed preferences, explicit/inline/remote config and other host plugins cannot
override the fixed definitions or guard composition. This check does not read any
of those private global inputs or attest them; no reload/settings edit is needed.
Actual effective catalogs, native identity and executor guards still need future
native proof. Same-user adversarial filesystem races are not sandboxed.

Definitions then stay FIXED: no subsequent config/agent/plugin edit or reload.
Typed tools and generic-executor guards register while `native-host.json`, registry,
routes and pointers are absent. There is no startup bridge/Knowledge/session call
or database creation in fixture mode. Pending typed operations refuse before any
native read/effect. All three catalog hooks still enforce exact role tools;
fixture-chief and unknown generic executors deny, unlike the production chief.

Fixture automatic startup AND event reconciliation are disabled for its entire
lifecycle, including after successful native identity checks or a sealed binding.
No server.connected/execution event may open the bridge/store or replay an action.
File readiness/sealing is not identity authority. Each fixture bridge admission
requires a successful actual native caller check in the current serialized typed
turn and rechecks source/config/runtime/managed pins. Failed/missing native identity
and pin drift refuse before a new bridge/store/managed/send effect. Already admitted
operations still have the R1 unknown-outcome/late-effect limits below. Production
startup/event recovery and chief rights are unchanged. Automatic fixture recovery
is explicitly deferred: the future controller must use guarded real native
operations, not isReady(), file bindings or replay of pending work.

Actual installed code anchors (read as text, not executed): CLI bytes
117110819–117121344 (`vZ`: options/location, unary session methods, transforms),
121367000 onward (default definition loader), 120710000 onward (ancestor discovery);
app.asar `@opencode/schema/dist/config{,/agent,/plugin}.js` and `location.js` confirm
`agents`, `system`, `steps`, permission rules and `{package,options}`.
There is no execute-as-session RPC assumed here.

## Historical 3b31978 sequence — superseded by OPERATOR.md

1. Separate authorization/review chooses one bounded model and F, owns an effects
   manifest, and stages the FIXED definitions above before first native load.
2. Existing managed `session.create` (OpenChamber action, not a new endpoint) creates
   exact fixture sessions with directory F/home or F/lead-a/F/lead-b and agent
   proof-desk/proof-chief/proof-lead-a/proof-lead-b. Omit prompt initially, goals,
   worktree and delegation; at most four active sessions. Retain actual returned
   session IDs. Inspect actual native Session.Info for ID, agent, projectID,
   unarchived state and exact location. If managed output lacks these fields, the
   native lifecycle observer must read `ctx.session.get({sessionID})` (unary, 4s
   observation), NOT invent fields or use metadata as identity. Read the exact
   scoped managed Knowledge list for each owned directory; retain returned projectId,
   separate from Core projectID. Missing/ambiguous readback stops, never retries create.
3. Trusted OPERATOR (not model enrollment) writes only runtime `home/desk/` state
   and fixture desk.json/chief.json. Native config and agent prompts remain untouched.
   The JS factory's load/caller and Python NativeStore.config/transaction/authority
   reread state per operation. New fixture `ready()` validates the complete set and
   seals its exact bytes on the first tool operation. Missing/malformed partial
   binding refuses with no effects and can be completed by the operator; after
    successful sealing, any runtime edit refuses. Sealing is not successful native
    identity verification and never enables event recovery. Each location seals independently;
   trusted operator must finish the complete set before ingress. No file is an
   attestation: actual tool calls still check native get, exact input/context and
   managed list projectId. Forged IDs cannot authorize a filing.
4. Managed `session.send` may later start owned turns by exact actual sessionId.
   Models must invoke registered desk_report/desk_inbox (then sync if needed).
   Entry capture holds the UNCHANGED actual c only on those registered executions,
   host-private, at most sixteen captures/location. It cannot be called by a model
   enrollment/admin tool; it does not expose a ticket or manufacture c. These
   references alone are not proof; direct canary probe/result collector is MISSING.
5. Future first-smoke controller must have a 120s aggregate deadline, 4s/call,
   <=128 owned events, abortable subscription, no goals; stop on unknown outcome.
   Before projections: capture final actual role catalogs and actual generic
   read/write/managed executor denials using ONLY an owned EMPTY host-canary and
   exact supported descriptors, with captured native c. No shell/admin/general
   executor path. Observe actual tool parts by message/call/name and correlate
   exact session, agent, location, Core/Knowledge IDs, host input/action admission
   and result IDs. Compacted/missing exact records stay uncertain.

Steps 2–5 are an invocation PROTOCOL, NOT an implemented controller command. No
supported native API was shown impossible: operator binding + unchanged definitions
is grounded and the pending->bound seam is implemented/tested. Exact remaining code:
operator manifest/session-info/namespace collector and guarded runtime writer;
host-private captured-c canary executor-denial probe for installed descriptors;
bounded event/tool/admission/Knowledge-guard/result collector and smoke verdict.
Current capture has no probe/driver/readout API. Do not substitute a direct import
of makePlugin with a constructed c. No actual staged native execution command is
ready; session.create/send actions above require the missing reviewed controller.

## Historical first-smoke checklist at 3b31978

The checkpoint intentionally accepts NO routine rules. Existing exact-report-hash
classification is unchanged: even a benign request without a trusted applicable
rule escalates. A reviewed fixture-owned exact full-report ack rule and its bounded
runtime validation must be added before a NO-chief-escalation smoke can be claimed.
Never weaken classification or call fixture decisions principal signoff.

Future manifest must retain F/path/source/config pins; four exact session identities
(this checkpoint requires lead B bound too, but idle during the first smoke); one report with stable ID/body/hash; native tool,
input/message/admission/action IDs; exact canary probes/results; status Note and
home-overview Note IDs/body/nonces/returned-ID persistence and exact list readback.
Only one project status Note plus home overview in first smoke. No Todo, Plan,
brief, real-chief memory/pointer, principal approval, UI refresh or Q95 dependency.
The first smoke does not prove backlog fairness (4/4, 32 windows), rotations,
interleaving, revocation, late effects, adoption, rollback or the full matrix.

## Stop, rollback and unknown outcomes

Stop fixture ingress first; retain every owned session/Note/action ID. Cleanup
root-wide aborts supported subscriptions and fences every loaded location. Returned
unresolved counts and quiesced=false are conservative; unary RPC MAY finish late.
A process-scoped root tombstone prevents replacement contexts/modules from bypassing
cleanup; it is not durable/cross-process cancellation. Never restart/reload to clear
uncertainty. No pending turn is replayed, deleted or recreated to make a test green.
Inspect exact native admissions/readbacks and ledgers; any interrupt/session cleanup
is an exact-owned-ID, separately reviewed operator step, not automatic rollback.
Sealed binding mutation/rotations are deliberately not implemented here. Retain
assets/evidence while unresolved. UI visibility remains separate settings authority.
