# Kit configuration

## Pi preset

`./install.sh --profile pi` composes Chief and the included lead using
`profiles/pi/profile.json`, shared role cores and the engineering/research packs.
Its explicit single-host preset is separate from scoped OpenCode manifests and
standalone `--lead-config`. Add independently selected `--pi-capability pi-subagents`
and/or `--pi-capability pi-goal-x`; other hosts, routing and lead-config cannot be
combined with it. Nothing is added to the default three-host installation.

Pi loads the rendered prompt templates from `~/.pi/agent/prompts` and namespaced
workflow skills from `~/.pi/agent/skills`. The fixed managed path/hash inventory
is `~/.config/chief-of-staff/pi-install.json`. Unowned, modified, missing-owned,
malformed-inventory and symlinked-descendant collisions refuse before writes or
removals. Updates can change selected capability guidance without adopting user
files. Courtesy has its own immutable inode/hash receipts. Uninstall requires no
packages or selected capability flags and removes only validated owned resources;
brief seeds, package settings and unknown files/directories remain.

The default Pi agent directory is required. `PI_CODING_AGENT_DIR` overrides are
refused; disabled discovery or extension command collisions need operator
reconciliation. Pi's brief must be an absolute path inside the selected HOME,
without linked descendants. Installation is preflighted and replaces files
individually; it isn't a multi-file transaction or a concurrent filesystem sandbox.
See [Pi setup and exact upstream interfaces](../docs/pi.md).

Chief instructions live in `chief/`; the independent lead core, adapters, log template and checkpoints live in `lead/`. `shared/` supplies short Docket and Fleet references. The renderer combines these with `profiles/technical/` and named practice packs. Unknown templates, slots and packs fail closed.

## Standalone config

`./install.sh --lead-config examples/principal.json --print opencode` renders a lead without Chief memory. Omit `--print` to install it. The configuration has exactly four fields:

```json
{
  "version": 1,
  "agent": "study-lead",
  "packs": ["research"],
  "owner": {"mode": "principal", "style": "Short plain outcome summaries."}
}
```

Agent names use lowercase letters, digits and hyphens, start with a letter and have at most 48 characters. `lead`, `chief-of-staff`, `shape` and `checkpoint` are reserved. Packs are a nonempty unique list of `engineering` and `research`, optionally with `upstream-courtesy`. Removed `life-admin` selections fail explicitly. Courtesy contributes no default prompt text; its skill loads on demand.

The two reporting modes are:

- `principal`, with an explicit nonempty `style`: report directly in the conversation.
- `agent`, with an absolute `pointer` and plain-language `label`: re-read the pointer's `session` and `directory` for each send. Missing, invalid or unavailable pointers block delivery. Ask the principal; don't guess a recipient or resend an uncertain delivery.

For example, an agent owner can be `{"mode":"agent","pointer":"/configured/owner.json","label":"research coordinator"}`. This is kit configuration; it doesn't create an authenticated host binding.

With no explicit host, standalone mode installs OpenCode, Claude and Codex lead files, a namespaced `<agent>-checkpoint` and the discoverable courtesy skill. It doesn't seed Chief memory, install helpers or services. `--routing` cannot be combined with standalone mode.

Standalone and scoped installers preflight all outputs. The selected HOME may be an alias, but descendants must have no `..`, linked child ancestors/leaves or nondirectory parents. Unowned targets are refused. These checks don't prevent concurrent filesystem replacement races or provide a multi-file rollback transaction. Uninstall preserves logs/private seeds and refuses modified scoped managed files.

## Optional desk

The desk stores reports and receipts in SQLite, resolves an explicitly enabled per-project reporting route and prepares progress projections. Chief's `chief.json` remains the authority pointer; the desk route has a separate identity and epoch. A report receipt doesn't grant approval. Existing leads need an explicit reporting-contract update and acknowledgement before switching routes.

For an already-created disposable root, inspect the separate desk install:

```sh
python3 scripts/install-desk.py --root "$SCRATCH" --home "$SCRATCH/chief" --mode print
```

`--mode install` writes managed modules and private seeds there; `--mode uninstall` removes only unchanged owned modules and retains state. It doesn't update default agents or start a service.

`scripts/desk.py --home <configured-home>` accepts stdin JSON for data operations. `status` and `audit` inspect the store. `file-report` accepts `{report,context}`; context alone is an untrusted hint. Registered identity admission needs a trusted verifier. `--operator` is an accidental-use guard, not authentication.

Durable receipt/audit/outbox transactions precede acknowledgements. Failed projections remain pending, unknown reports are quarantined and uncertain sends aren't replayed automatically. Per-project Knowledge notes are the primary progress projection; lead plans remain lead-owned. Brief writes require an explicitly enabled cooperating-writer protocol and expected revision. Neither direct filesystem writes nor model labels authenticate a decision.

Bounded rules in `scripts/desk_rules.py` accept tightly typed technical choices or exact recorded relays with current authority, scope, expiry and version pins. Reserved decisions escalate. Schema validation can't detect every risk hidden in free text; the fictional corpus isn't evidence of classifier reliability.

The [filing-only receiver](chief/desk/filing/README.md) prepares landed/next/your-part status and bounded digests, forwarding visible questions to Chief. It preserves pending/uncertain native outcomes for reconciliation. [Native host adapters](../hosts/desk-native/CONTRACT.md) require operator-supplied identity bindings, catalog checks and explicit activation. Default installation enables no desk route or native Knowledge writes.

## Scoped profiles

`--profile technical` keeps the default host layout. `--profile example` or a JSON manifest creates a separate local OpenCode/home bundle under `~/.chiefs/<id>`. Scoped Claude, Codex and remote profiles aren't supported. Scoped mode cannot combine with `--lead-config` or `--routing`.

Use `profiles/example/profile.json` as the manifest. It supplies integer version 1, id, responsibility, home, distinct chief/lead/worker agent names, lead packs, remit, tone and adapter. The supported adapter is `opencode-local-notes-a2a-v1`. Supply the separately installed transport explicitly:

```sh
CHIEF_A2A_MODULE=/configured/opencode-a2a/src/plugin.js ./install.sh --profile example --print
```

Review output before installing without `--print`. The installer pins the transport hash. The bundle imports this checkout's adapter; retain its location or reinstall after moving it. Uninstall uses the managed inventory and doesn't need the external transport file.

`CHIEF_A2A_MODULE` is required for install, `--print` and `--dry-run`; it must be an absolute path to the approved transport module. The installer resolves it to a canonical file URI and records its SHA-256. Runtime still checks that pin and the canonical tool descriptors before capture. Uninstall ignores transport settings, including a missing file, and retains private seeds. Modified or unowned managed files block updates and removal until reconciled.

The opt-in `scripts/test-domain-native.mjs` and `scripts/test-result-adapter-native.mjs` require absolute `CHIEF_OPENCODE_BINARY` (the host executable), `CHIEF_A2A_ROOT` (the transport checkout) and `CHIEF_NATIVE_TEMP_ROOT` (an approved existing scratch directory). They pass that root's `src/plugin.js` as `CHIEF_A2A_MODULE` to their isolated installer. If both transport variables are present, installation rejects different selections. These scripts start a real host and are separate from offline packaging checks.

Default and scoped installs copy only the seven service README guides into `<chief-home>/.kit-resources/services/`. References use absolute installed paths; the index's relative guide links stay within those copies. OpenCode permissions allow reads of those exact files and deny edits and reads of resource siblings. The copies contain no service executables, credentials or private registry data. Claude/Codex permission enforcement remains host-specific as described in the root guide.

Scoped guides join the existing owned inventory and runtime managed-path guard. Default guides have a separate exact-hash inventory, preflighted before other default writes. Existing installs can add absent guides; collisions or modified copies require reconciliation. Uninstall removes only unchanged owned guides, retaining private memory. Removing one default host retains the guides while another installed host still uses them.

The example starts with deny-all permissions and exposes a narrow memory/research/identity/guarded-a2a catalog. Shell, Code Mode, raw a2a and native subagents are denied. Chief can create scoped leads; leads can create scoped workers. Same-role replacement requires the same directory. Owner sends resolve the current pointer. Missing or unexpected transport binding fails closed.

These are host tool/permission boundaries. They don't isolate same-user processes, hostile trusted plugins, API credentials or filesystem replacement races.

### Operator goal binding

Goal mode belongs to OpenChamber; a2a has no goal option. `domain_lead_start` uses a separate operator-owned binding outside model-readable homes. It fixes the lead agent, concrete model, outcome directory and goal metadata. Unknown, timed-out or partial creates leave an outcome lock for reconciliation; never retry them blindly.

For an installed example, an operator can create a private binding using `scripts/bind-goal.mjs` with `--home`, `--lead-agent`, `--binding`, a literal loopback `--origin` and either `--desktop-settings` or `--auth-file`. Parent directories must be real, operator/root-owned and not group/world-writable; auth/binding files must be regular, nonsymlink, single-link and private (0600 or 0400). Keep tokens out of prompts and this repository.

Setup reads authenticated system identity and writes an exclusive binding; it doesn't start a server or send a prompt. Runtime rechecks instance identity, caller location, created agent/model and persisted goal metadata. Restarted servers or expired credentials fail closed. Rebinding needs explicit operator reconciliation; keep outcome records and locks. A configured host still needs its own native validation before using this workflow.

## Worktree hygiene and shared services

Sessions stay in the project folder unless the principal explicitly requests a move. Engineering workers can use worktrees within it. Lead instructions cap registered secondary worktrees at eight per repository, retain branch refs and protect dirty, ignored, unknown-owner and active work. Checkpoint/handover records retained worktrees and reasons. No force cleanup is authorized.

Configure Docket and Fleet checkout locations before following their shared references. Model policy/routing is optional for independent leads. Service references don't authorize scheduling, external contact, downloads or new background jobs.
