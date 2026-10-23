# Effective management context

The normal OpenCode installer installs `services/role-context.mjs` as the discovered
`chief-role-context.js` plugin. It registers only a supported request-context hook:
excluded direct tool schemas are removed; the hook changes no permissions, systems, models, goals,
MCP connections or plugin lifecycles. Build/general/explore keep their
coding base and tools. Existing nonempty chief/lead agent bodies already replace
the native provider base; no second native management-prompt mechanism is needed.

`services/role-policy.json` is the canonical exact exposure policy. Normal role
generation adds its declared-action denials to chief/lead permissions; rendering
embeds the same tool lists into the installed JavaScript plugin, with no runtime
JSON dependency. Role-level `execute` denial removes both the actual execute
schema and Code Mode catalog before native instruction assembly. Deleting only
the late hook's execute schema would leave the injected catalog behind.

Chief/lead keep read/grep/glob, patch, shell, skill, OpenChamber, Knowledge, a2a,
Runway and required direct chief/heartbeat tools. Patch is the observed harness's
sole native editor: retaining it is the minimal functioning-editor exception,
not permission to widen edits. Own-file/Plan grants and secret/foreign restrictions
stay intact. Unused web, display, schedule and coding/delegation schemas are removed.
Native edit/write registration alone is not evidence those tools reach this harness.

Actual specialist Galley writers use custom agent IDs, an owner-generated nonempty
author body and deny-all permissions with narrow edit/read/shell/contact exceptions.
They already deny Code Mode and replace the native coding base. Leave their author
skills/taste intact as a measured control; generic `writer` is not that inventory.
Dispatcher is likewise an already-narrow resolve-only control. Build workers keep
native coding context and tools.

The Claude bridge 1.4.1 boundary is separate: ordinary requests retain the Claude
Code SDK preset and append the supplied role instructions. No exposed supported
custom systemPrompt setting replaces that preset. SDK builtin tools are already
disabled with `tools: []`; forwarded request tools form its MCP surface. Shorter
role bodies and tool filtering therefore trim effective context but do not remove
the SDK preset. No cache patch, provider-global change or private prompt surgery.

Acceptance requires fresh matched first-request usage and actual required-function
checks per role. Source tests establish policy/rendering, not final runtime savings
or later harness hook behavior. Keep baseline/AFTER measurement separate from counts.

## Install-time permission compiler

The operational installer imports `scripts/role_context.py`:

- `compile_denials(role, registry, allowlist, *, tool_actions=None)` returns
  `{role: [exact deny rules]}`. Optional `tool_actions` maps exact tool IDs to verified
  declared permission actions; `None` explicitly records direct-schema-only coverage.
  Unknown excluded tools without this classification are refused, not identity-guessed.
  The same keyword is accepted by append_denials, amend_header and prepare.
- `append_denials(existing, role, registry, allowlist)` preserves every original rule
  and order, appending only absent exact denies.
- Both inventories are `{tools: [exact IDs], skills: [exact IDs]}`. Supply fully loaded
  native **and harness-advertised** IDs, with provenance in the rollout manifest.
  Native `skill.list()` alone was only two entries in the observed Location and is
  NOT a complete harness skill inventory. Missing reviewed dependencies, duplicates,
  patterns, invalid types and unsupported roles fail compilation. Inventory lists
  alone cannot establish discovery completion: the installer owns that attestation.
- `prepare(path, role, registry, allowlist, expected_sha256)` is dry-run; it returns
  path/role/beforeSha256/afterSha256/afterText. Only existing canonical managed agents
  are accepted. All non-permissions header bytes and the entire body are preserved.
  Existing YAML/inline-JSON permission lists are supported; JSON frontmatter is refused.
- `apply(manifest, new_backup_path)` checks hashes, creates a private absent-only byte
  backup and atomically replaces one file, returning a receipt.
- `rollback(receipt)` restores only the exact installed postimage; subsequent owner
  changes cause refusal. The operational driver preflights/co-ordinates multiple files.

No function grants access. Tool IDs are NOT necessarily permission actions:
`patch`, `write`, `edit` and native `opencode_worktree_remove` all use **edit**.
The compiler never blanket-denies edit to hide one tool: existing own-path edit rules
remain unchanged. Other shared actions used by an allowed tool likewise are not
blanket-denied. A direct-schema exclusion is not an independent execution boundary.
Native actions come from official V2 permissions documentation and the declared
installed tool metadata; verified MCP actions use normalized server_tool names.
Custom registrations without declared permission metadata remain direct-schema-only
(explicit None mapping); do not invent an action from their tool name. Existing fictitious
native alias rules are refused for owner reconciliation rather than silently removed.
Tool-specific checks decide execution; metadata readback is not proof of call denial.
New catalog entries require a reviewed inventory and normal installer rerun.

## Role dependencies

The direct hook covers chief, lead and resolve-only heartbeat-pilot-dispatcher.
The writer's actual dependencies must come from the writer Location's loaded inventory,
not guessed `galley_*` aliases. Configure plugin `options.roleTools.writer` with the
reviewed exact allowed IDs; until supplied, writer direct tools are preserved rather
than removing an unknown required dependency. The same `roleTools` map can override
other role tool lists. Galley remains owner of writer permissions/agent generation.
Chief skills are checkpoint, reset-*, upstream-courtesy, shape and deep-research;
expand patterns to exact observed IDs before passing the compiler its allowlist.

## Corrected evidence: fresh catalogs and existing-session updates

The original hosted investigation reused a session and searched initial system names
without observing message updates. Its host-gap conclusion is **withdrawn**. Independent
plain OpenCode 2.1.3 evidence shows fresh denied skills are omitted; existing sessions
retain their initial catalog history followed by explicit skill revocation updates.
Historical name presence alone is not current availability or a host defect.

The earlier worktree test denied the fictitious opencode_worktree_remove action, not
its actual edit action. With edit denied, plain 2.1.3 omits that tool; this rollout must
NOT deny edit globally because required own-file editing shares the action. Preserve
resource-based edit policy and use direct-schema filtering where independently possible.

Required nested resource listing executed in the historical hosted check; no excluded
call was tested. Final measurement uses fresh matched no-effect sessions, with IDs-only
catalog and message-update observation for the lead. Do not infer denied execution
from metadata, or savings from historical system-name scans. No upstream bug has been
established; no host fork, provider-catalog text surgery or probe campaign is authorized.

## Can unused servers/plugins be disconnected per agent?

No per-agent server/plugin lifecycle mechanism is documented in official V2:

- [MCP servers](https://opencode.ai/v2/docs/mcp-servers) exposes `mcp.servers.<id>.disabled`
  at configuration/Location scope. Per-agent tool permission denies hide/deny tools
  **without disconnecting the server**. Documentation says server instructions are
  omitted if all its tools are denied (or Code Mode execute is denied). Evaluate actual
  permission actions and instruction updates. Chief/lead required tools are direct;
  their execute denial is intentional. Roles needing nested tools require separate review.
- [Plugins](https://opencode.ai/v2/docs/plugins) configures plugin arrays and removal
  IDs at global/project scope. A plugin option named `agent` is plugin-specific input,
  not a generic per-agent lifecycle switch.
- [Plugin API](https://opencode.ai/v2/docs/build/plugins) exposes Location-scoped
  MCP transforms/reload and per-request hooks, not per-agent MCP connections/unloading.

Therefore restrict exact tools per role and filter direct schemas; do not globally
disconnect Canvas/render/web/schedule providers to slim a lead. Those names may be
tools provided by one shared plugin, not separate MCP servers. Preserve required
dispatch, memory/plan editing, writer and dispatcher dependencies.
