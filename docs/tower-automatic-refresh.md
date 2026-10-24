# Local Tower refresh (source-only integration)

The existing Tower host runs `scripts/tower_refresh.py` using its operator-pinned
Python/script/config paths. No new service, scanner, listener, shell, network auth
fallback or native wake. The normal Docket client uses its existing discovery/auth;
no OpenChamber URL/token/session is persisted. The subprocess environment is reduced
to HOME/PATH/LANG/LC_ALL. No event selects a command, config, path or origin mapping.

## Operator configuration

No real private config is shipped. An operator must create an exact bounded JSON
config with `version:1`, `export_config:{root,path}` (existing exporter allowlist),
optional `manifest:{root,path}` (only matched statuses change), optional
`docket:{executable:<canonical normal Docket CLI>}`, and `projects` (max100).
Each project contains exactly:

```
project_id: existing export project ID
session: original registered lead session
directory: original canonical project directory
header: {root: approved canonical source root, path: exact Markdown path,
         redact_private_patterns: optional strict boolean}
copies: [{source:{root,path}, target:{root,path},
          redact_private_patterns: optional strict boolean (Markdown only)}, ...]
migration: optional {sha256: exact header digest, status: reviewed plain status,
                    summary: existing strict summary with actual observed_at/evidence}
```

Copy targets must match existing project's file/image allowlist. All roots/path
components use existing no-follow/size/link/privacy gates. Raster signatures checked;
same512KiB file bound applies. No directory enumeration. Parent must explicitly
approve source/destination mappings and source digests; never map an original as a
target. Destination directories must already exist. Missing/invalid caches fail
closed. Source privacy failure completes no writes. All reads/validation precede
writes; individual replacements are atomic0600, **not** a cross-file transaction.
Redaction defaults to refusal. Only a previously reviewed **exact text mapping** may
opt in with `redact_private_patterns:true`; header/copy opt-ins are independent.
Only existing SECRET-regex matches become `[redacted private-pattern text]`, including
new runtime matches; nothing else is removed. Sanitization runs again on output.
Original source bytes remain untouched and supply migration/source hashes. A redacted
principal sentence is not adopted as a capability. Safe result `redactions` counts
substitutions across copy/header processing, without logging matched text; no new
projection schema fields. Do not enable this on broad roots or raster mappings.

I/O failure can leave a partially advanced collection; retries converge without
manufacturing events. Config-file flock serializes startup/event/agent-context work;
do not replace the operator config during a refresh (trusted ancestry assumption).

Plain headers require Status/Usable now/Left/Waiting on each <=100chars and explicit
Needs you true/false; Handed to is optional. Obvious hashes/IDs/paths are refused as
principal text, not translated. Source digests preserve observation age on unchanged
content. A digest-bound initial reviewed migration can seed a legacy header. Changed
invalid source retains prior summary/time and appends the fixed concise stale-source
cause/recovery to summary provenance; Tower exposes that cue. Manifest updates status
only, preserves unrelated entries/fields. No summary.status extension.

## Native Knowledge

Only optional strict `knowledge.observed_at` is new; kit mirrors optional strict
`summary.needs_you`. Genuine `tower_export.py` API reads record actual observation
time. Automatic refresh copies the exact validated prior Knowledge section unchanged.
Notes/todos age is displayed separately from current documents and source summaries.

During ordinary chief/lead work or checkpoint, run explicitly in genuine inherited
agent context:

```
python3 -B ~/.local/share/chief-of-staff/tower/tower_refresh.py --knowledge ~/.chief-of-staff/tower/refresh-config.json
```

Parent installs the reviewed modules in that existing runtime directory and seeds
only the exact private config convention above. Normal chief/lead roles direct real
work to reset-checkpoint for this command; missing script/config skips with a gap
report, never creates/discovers another config or uses fallback auth.
This uses the existing supported adapter and **actual** caller; it accepts no caller
ID/credentials. Original directories come only from operator mapping, not events.
Mapped source plan files are checked against exact API paths. Failed auth/access
preserves the entire old cache/time. The checkpoint instruction is supported normal
context work, **not an automatic hook** and not a recurring model wake. Background
notes/todos reads are deliberately not promised (chief accepted true-age cache).

## Docket and Tower integration

Decided Docket source contract v1: fixed normal executable, argv tails
`project-markers --json`, `tower-refresh show --json`, and
`tower-refresh ensure --until <aware deadline> --json`. No real CLI invocation in
source verification. Strict complete marker envelope (max20/64KiB) is authoritative;
nonzero/malformed response is unknown, never empty. Known marker origin maps to the
configured project/outcome, returned `mil_` ID dedupes, source milestone_at is retained,
and neutral `New work was delivered.` labels the landing. Current usable-now prose is
not historical source-time evidence and is never attributed to an old marker.
Unknown origin drops. Hold/done
are read-only observations, never resumes or acceptance. References over Tower's500char
limit use marker ID plus exact reference digest rather than altering schemas.

Periodic notices create no activity. Authoritative marker reads on each configured
refresh repair missed best-effort invalidations. Explicit source events are
`ev.docket.snapshot.refresh_due` / `docket.snapshot.refresh_due` and
`ev.lead.milestone.recorded` / `lead.milestone.recorded`, source `docket` only.
Refresh occurrence identity/time/purpose/item/provenance and marker source-time are
checked before sending sanitized stdin. Coalesced is Docket's integer skipped-slot count.

Tower config sections `project-snapshot-refresh` and optional
`project-snapshot-startup` have the same exact fields: `python`, `script`, `config`
(canonical absolute operator-pinned paths), `item_id:"dkt_tower_refresh"`.
Missing config is inert. Handler uses existing host durable retry/DLQ behavior; startup
is one-shot and returns even on failure (no watcher restart loop). Subprocess timeout60s,
stdin16KiB/output32KiB; Docket calls8s/output64KiB. Logs include counts, never source bodies.

Lease show/ensure uses only this fixed normal client. Renew at startup/event only when
under7days, extend89days (within90), retain anchor. Cancelled never resurrects, including
queued old notices. Expired leases require explicit owner renewal, surfaced as a fixed
failure; do not silently auto-revive. Missing lease can be created only once this
operator-enabled path is installed. No own renewal scanner. Queue enqueued/accepted is
not broker/page proof. Docket must install its source contract before enabling this.

## Parent install and rollback

Parent seeds reviewed configs/migrations/cache observation ages; scans source, merges,
installs scripts+Tower through normal workflow preserving role metadata, then enables
only these exact host config sections and the fixed Docket lease. Parent owns real
scheduled/milestone observations, phone captures and chief review. Source tests are
not proof of installed freshness. Never replay milestone calls or create fake answers.

Rollback disables only the new two host sections, cancels only `dkt_tower_refresh`
through normal `tower-refresh cancel --json`, and restores exact owned script/config
preimages if necessary. Do not restore whole Docket state, foreign records or original
project files. Cancel cannot retract an already queued notice. Preserve prior snapshots
and caches until deliberate operator replacement.
