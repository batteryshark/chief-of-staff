# Tower kit v1: source and scoped release

These are manual source tools, not an installed service. Parent owns the real project manifest,
exact-file/content privacy review, first refresh, deployment and phone proof. No personal-root
discovery, backing-store reads, new credentials or unattended freshness claim is made.

## Question status

Proposed installed Docket argv (no shell, arguments or caller-selected options):

```json
["/absolute/installed/node","/absolute/operator-home/.local/share/chief-of-staff/heartbeat/chief-question-status.mjs"]
```

Parent resolves the absolute installed binary and module paths and verifies their preimages
before release. The entry reads only the operator-owned fixed
`~/.chief-of-staff/heartbeat/pilot-options.json`, with `Bus.inbox()` / `detail()`; it never
ACKs, closes, answers, dispatches, wakes or calls HTTP. Input is exactly the agreed v1
session/directory/goal object (4KiB); deadline 4.9s inside Docket's 5s timeout; output32KiB.
Malformed input exits nonzero with no output. Unknown source gives complete:false, no bodies.

Coverage is an explicit operator assertion in those options, never enabled by installation:

```json
{"questionCoverage":{"version":1,"scope":"registered-chief-post","since":1792700000000,
 "origins":[{"session":"ses_example","directory":"/approved/project"}]}}
```

Example only, NOT real coverage. `since` is the observed installation boundary, no later
than now, even for an unchanged older goal. Only bound posts at or after `since` count;
an unresolved precoverage, legacy, unbound or ambiguous record remains incomplete.
Only registered chief_post coverage is claimed; direct chat/unstructured asks remain outside
this assertion. Parent must not assert comprehensive coverage without an established source
boundary. Absent/late coverage, missing journal, legacy/unbound open records, source errors,
unknown lifecycle, or bounds violations yield incomplete, not a fabricated empty set. Old
records are never rebound. Native session/Location and app goal `id`+`createdAt` milliseconds
are captured at posting through existing supported reads; stored `created_at` is an explicit
mapping. Missing metadata preserves posting/fallback as unbound. No goal mutation occurs.
Answered, covered, filed and closed records are not unresolved even when delivery is uncertain.
Docket retains its native identity/freshness/hold/continuity gates and owns enabling its helper.

## Chief-only acceptance

Existing `chief-nod ask` takes `--accept-project PROJECT_ID --accept-outcome OUTCOME_ID`
and `--reference SAFE_OUTCOME_REFERENCE`. Its normal fresh chief-pointer/native identity gate
and ask binding remain mandatory. A lead gains no issuing authority. Supply a normal linted
one-question card with exactly these options, in this order:

```json
[{"id":"accept","label":"Accept","description":"Accept the finished outcome."},
 {"id":"not-yet","label":"Not yet","description":"Keep this outcome open."}]
```

Normal recommendation/default/600-character rules still apply. Labels remain exactly Accept /
Not yet; recommendation stays in the body. Request identity derives from project/outcome,
chief binding and rendered payload; supplied dedupe/idempotency keys are refused. Intent is
durable before POST, binding before announcement; deduplicated creates are not adopted.
Existing Tower-announcement versus origin-runner fallback is unchanged. No card was sent here.

Normal existing reconcile saves actual request snapshot and decisions. The read-only command
`chief-nod acceptance-status REQUEST_ID` projects only a registered chief-issued acceptance.
It uses actual Nod request creation and answer ID/time, not local intent or delivery time.
Pending/expired/cancelled are not answers; multiple conflicting answers/unknown lifecycle are
refused. Answer includes exact nod.answer type, request/project/outcome binding, reference and
provenance. Delivery/ACK uncertainty cannot turn an actual answer back into an unanswered ask.
Nothing grants inferred acceptance, executes an effect or resumes a held goal. Earlier accepted
decisions are not replayed or adopted for another outcome.

## Manual Knowledge and semantic projection refresh

`scripts/tower_export.py` consumes one private approved config:

```json
{"version":1,"projects":[{
 "project":{"id":"demo","outcome_id":"outcome-1","title":"Example","status":"active",
  "root":"/approved/project","header_file":"lead",
  "files":[{"id":"lead","label":"LEAD.md","path":"LEAD.md"},
   {"id":"plan","label":"Native plan","root":"/approved/exact/plans","path":"named-plan.md"}],
  "images":[{"id":"diagram","path":"images/diagram.png"}],
  "export":{"root":"/approved/exports","path":"demo.json"}},
 "knowledge":[{"id":"native-note-id","kind":"note","title":"Decision"},
  {"id":"native-todo-id","kind":"todo","title":"Next"},
  {"id":"native-plan-id","kind":"plan","title":"Plan","file_id":"plan"}],
 "summary":{"observed_at":"2026-10-23T18:00:00Z","provenance":"current owner status",
  "reference":"native-note-id","usable now":"Source ready","left":"Integration"},
 "activity":[{"id":"commit-abc123","project_id":"demo","outcome_id":"outcome-1",
  "kind":"landing","at":"2026-10-23T17:00:00Z","label":"Source landed",
  "reference":"commit abc123","provenance":"Git commit"}]
}]}
```

Examples are not shipped runtime data. Optional `acceptance_request_id` selects the exact
chief-issued request; acceptance itself cannot be supplied in config. Summary/activity require
factual sourced times/references; no prose mining, filesystem mtimes or invented receipts.
Summary is only the explicitly sourced legacy-header migration seam, never owner acceptance.
Project/files/images match Tower's exact manifest entry. Knowledge is an additional exact
native item-ID allowlist; titles are sanitized operator choices, IDs and todo booleans remain
native. Native notes use `body`; native todos use `text`, mapped exactly to projection `body`.
Missing/wrong-type todo text is unavailable, never rescued from a legacy body field.
No items are selected implicitly. Plan body is read only when native returned path
equals its separately approved file mapping; no directory sweep or arbitrary model path.

The reader uses only inherited loopback OPENCHAMBER_AGENT_TOOL_URL/TOKEN in memory and actual
OPENCODE_SESSION_ID, POSTing openchamber_knowledge/knowledge.list with approved directory.
No caller/session override, redirect, proxy, remote origin or other action is supported.
Socket timeout5s, response512KiB, schemaVersion1/ok:true/action/envelope checked. Missing
auth, malformed data or invalid selected records yields Knowledge unavailable, not substitute
content. Parent refreshes from a genuine inherited agent context; no credential file is made.
Native schema metadata outside selected items is not exported.

Strict nested v1 output is validated before writing, including IDs/types/unknown fields,
timezone-bearing nonfuture times and all outcome/request/answer/time bindings. generated_at
is sampled after Knowledge and saved-acceptance reads, not before the evidence it timestamps.
Each output is
atomic, private0600, fsynced with its directory; a failed replace preserves old bytes. The set
of projects is not a multi-file transaction. No-follow exact files/hardlink checks and text
secret-pattern refusals supplement, NOT replace, parent's exact-content privacy scans. Do not
allow operational private receipts merely because a filename/regex passes. Output max512KiB.

## Minimal dependency inventory and installation proposal

No blanket `install.sh` / heartbeat installer or role refresh is authorized by this source slice.
Nod loads an owned private `nod-options.json` in the rendered chief brief directory on each
ordinary call. Only the path is rendered into the script; URLs/retired IDs stay in this local
runtime JSON, never generated source. No shell exports are needed. Parent must preserve real
existing endpoints and the full protected retired-ID set before helper cutover. Generic fresh
users explicitly configure `retired_sessions:[]`, not an imaginary retired identity. Missing
configuration or malformed/unsafe existing file fails closed; there is no inferred empty set.
No credential or actual operational value is generated here. Household-wide public sanitization
is parent-owned. The normal kit renderer/installer leaves this operator-owned JSON alone.
Parent first records hashes/modes for every chosen existing target and exact options/config
preimages; absent targets are recorded as absent. Stage same-directory new files, verify byte
hashes and modes, then atomic rename. New dependencies must land before importing files.

1. Existing heartbeat directory: new `question-status.mjs`, new `chief-question-status.mjs`,
   changed `bus.mjs`, `goal-wait.mjs`, `plugin.mjs`. Other relative plugin imports remain the
   already installed heartbeat modules. All use Node built-ins, no npm package addition.
2. Render ONLY `scripts/chief-nod` through existing `render.render(..., actual_chief_directory)`;
   review staged output, configure its fixed local JSON as below, then atomically replace only
   `~/.local/bin/chief-nod`, retaining executable mode. Never copy its unrendered template.
   Do not touch Nod state, credentials or old requests.
3. Copy only `tower_export.py` and `tower_schema.py` side by side into
   `~/.local/share/chief-of-staff/tower/` (Python3 stdlib only). Parent supplies the scoped config
   and output directories. Proposed refresh argv, in actual inherited agent context:
   `python3 -B "$HOME/.local/share/chief-of-staff/tower/tower_export.py" "$HOME/.chief-of-staff/tower/approved-export.json"`.
4. Lead prompt source `kits/reset/lead.md` is generated by `scripts/lean_roles.py`; parent
   separately reviews exact targeted role-body updates. No role config or live agent edit here.
5. Only after reviewed install/readback does parent hand the exact helper argv to Docket owner;
   any coverage assertion and Docket config/runtime enabling remain separate release effects.

Staging commands (parent proposal, NOT run here; SOURCE/STAGE are explicit reviewed directories):

```sh
install -m 600 "$SOURCE/heartbeat/question-status.mjs" "$STAGE/question-status.mjs"
install -m 600 "$SOURCE/heartbeat/chief-question-status.mjs" "$STAGE/chief-question-status.mjs"
install -m 600 "$SOURCE/heartbeat/bus.mjs" "$STAGE/bus.mjs"
install -m 600 "$SOURCE/heartbeat/goal-wait.mjs" "$STAGE/goal-wait.mjs"
install -m 600 "$SOURCE/heartbeat/plugin.mjs" "$STAGE/plugin.mjs"
PYTHONPATH="$SOURCE/scripts" python3 -B -c 'import os, render; print(render.render("scripts/chief-nod", os.path.expanduser("~/.chief-of-staff")), end="")' > "$STAGE/chief-nod"
install -m 600 "$SOURCE/scripts/tower_export.py" "$STAGE/tower_export.py"
install -m 600 "$SOURCE/scripts/tower_schema.py" "$STAGE/tower_schema.py"
```

Parent verifies actual chief directory instead of assuming the example, chmods staged chief-nod
to the recorded executable mode, reviews preimages, and atomically renames only released files.
Rollback: disable/restore the separately owned Docket helper configuration first if enabled;
restore exact scoped options/config and installed-file backups/modes by atomic rename, removing
only targets recorded absent. Restore original plugin before removing its new dependency.
Keep Nod request ledger/answers and original project records untouched. Retain failed refresh
evidence privately; no replay, session/model/goal change, restart or new service is implied.

### Durable local Nod options: exact install/loading/rollback seam

`docs/nod-options.example.json` is the portable fresh-user example (loopback, no images, explicit
empty retired set). Copy it to ignored `local-nod-options.json` with mode0600, then edit only
that local input. It accepts EXACTLY version1, url, image_base, retired_sessions. No token/key
field is allowed. URLs reject userinfo/query/fragment; image_base is HTTPS or explicit empty.
Input and runtime files must be owned regular0600 files, no symlinks/hardlinks, max4KiB.

For migration, parent supplies existing approved Nod URL, image URL and ALL actual protected
retired IDs from the reviewed local installation; NEVER replace them with the fresh example.
This slice neither reads those actual values nor changes live options. Credentials keep their
existing separate runtime mechanism; no key/token is copied into this JSON or generated source.

After rendering the reviewed staged helper to the ACTUAL brief directory, parent runs ONE of:

```sh
python3 -B "$STAGE/chief-nod" configure "$LOCAL_INPUT" --expect-absent
python3 -B "$STAGE/chief-nod" configure "$LOCAL_INPUT" --expect-sha256 REVIEWED_CURRENT_SHA256
```

The first refuses an existing config; the second requires the exact existing file hash.
Updates cannot remove any previously protected retired ID. Validation/preimage/guard checks
precede replacement. A private local lock serializes configure calls; a0600 temp file is fsynced,
atomically replaced and its directory fsynced. Failed replacement retains exact previous bytes.
Success prints a confirmation, not the routing values. No card, credential read, ledger operation
or service change occurs. Malformed existing options require owner review, never automatic reset.

Each fresh process reads the JSON at the rendered path, including isolated ordinary invocations.
An existing file is authoritative even if legacy URL/retired-session environment variables are
present. Missing/invalid files NEVER fall back, even to an otherwise valid old environment:
that could silently lose additional retired guards or redirect a migrated endpoint. Existing
installations must migrate these routing/image/retired values to the reviewed JSON before
cutover; new fresh users explicitly configure the generic example. Token/channel environment
handling is unchanged. The superseded environment-only example is removed; historical private
local-install.env stays ignored, but is not a runtime routing mechanism for this helper.

Rollback: retain private exact script/config preimages, hashes, modes and absent/present record.
Restore the matching helper/config pair atomically at the scoped cutover, preserving the actual
retired guard throughout; restore old helper before removing a newly introduced options file.
If runtime JSON existed, restore exact reviewed bytes/mode rather than calling configure to
remove guards. Keep local input/backup private and ignored; never modify credentials or Nod
continuation state. The only new ancillary file is the owned private .nod-options.lock.

## Offline validation

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tests python3 -B -m unittest test_tower_export test_chief_nod test_chief_nod_continuation test_lean_install -q`
and `node --test heartbeat/*.test.mjs`. Optional TOWER_SCHEMA_FILE points to the reviewed
Tower `project_schema.py` for cross-validator compatibility, read-only and no service required.
Source tests do not prove installed helper availability, current data, phone rendering or acceptance.

## Interface skills release addition

`skills/interface-design/{norman,norman-audit}` are self-contained first-party MIT packages;
origin/license evidence is in their README and copied LICENSE files. `install.sh` now preflights
and installs them using `scripts/interface_skills.py` for selected OpenCode/Claude/Codex hosts.
Installer is create-only/idempotent on exact receipt-owned bytes, refusing foreign/modified
packages before any package change. No symlinks or local skill-repository dependencies.
Workers keep ordinary coding discovery; lead manifest includes both; chief manifest excludes
both and generated chief permissions explicitly deny them. No live catalog/role was changed.
For this scoped release parent can stage only these packages/helper and perform the helper's
check/install operations for the chosen host, not run the whole kit installer. Apply the
reviewed chief exclusions alongside shared catalog release; do not grow chief's trimmed set.
Skill bins declare Python>=3.11 (or uv selecting it); package installation itself uses stdlib
and never runs a bin or downloads a runtime. Rollback uses helper uninstall only while exact
owned files match; modifications are retained for operator reconciliation, never discarded.

Norman source walkthrough: refresh uses one explicit allowlist config, reports exported count,
and leaves generated_at/unavailable visible for interruption/freshness. Acceptance uses existing
ask/help/identity gates, exact named choices and durable saved answer, not a second card flow.
Question helper is a machine JSON protocol with intentionally no interactive options; its
bounded incomplete envelope is the signifier consumed by Docket. Source audit collector ran;
changed exporter --version is argparse-generated help, not an orphan despite the static flag
heuristic. Existing unrelated script findings were not acted on. No live UX/timing proof claimed.
