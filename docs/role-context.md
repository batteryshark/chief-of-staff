# Per-role restrictions and direct-schema filtering

The normal OpenCode installer installs `services/role-context.mjs` as the discovered
`chief-role-context.js` plugin. It registers only a supported request-context hook:
excluded direct tool schemas are removed; no permissions, systems, models, goals,
MCP connections or plugin lifecycles are changed. Build/general/explore keep their
coding base and tools. Existing nonempty chief/lead agent bodies already replace
the provider base; no second management-prompt mechanism is needed.

## Install-time permission compiler

The operational installer imports `scripts/role_context.py`:

- `compile_denials(role, registry, allowlist)` returns `{role: [exact deny rules]}`.
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

No function grants access. Rules use existing effective permission IDs. Tool-specific
checks still decide execution; metadata readback is not proof of call denial.
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

## Observed scope and known advertising gap

One native scoped investigation confirmed the direct excluded schema was absent and
required nested resource listing executed. Config-first excluded tool/skill DENIES
were visible in native agent metadata. However the final outgoing system still
advertised a denied skill and nested tool name. No denied call was attempted.
Do not claim full catalog removal, verified denied execution, or associated token
savings. Retain the advertising gap as an open host integration issue. No host fork,
text surgery of provider catalogs or further probe campaign is part of this rollout.

## Can unused servers/plugins be disconnected per agent?

No per-agent server/plugin lifecycle mechanism is documented in official V2:

- [MCP servers](https://opencode.ai/v2/docs/mcp-servers) exposes `mcp.servers.<id>.disabled`
  at configuration/Location scope. Per-agent tool permission denies hide/deny tools
  **without disconnecting the server**. Documentation says server instructions are
  omitted if all its tools are denied (or Code Mode execute is denied); the observed
  harness catalog gap above still applies. Do not disable execute when required tools use it.
- [Plugins](https://opencode.ai/v2/docs/plugins) configures plugin arrays and removal
  IDs at global/project scope. A plugin option named `agent` is plugin-specific input,
  not a generic per-agent lifecycle switch.
- [Plugin API](https://opencode.ai/v2/docs/build/plugins) exposes Location-scoped
  MCP transforms/reload and per-request hooks, not per-agent MCP connections/unloading.

Therefore restrict exact tools per role and filter direct schemas; do not globally
disconnect Canvas/render/web/schedule providers to slim a lead. Those names may be
tools provided by one shared plugin, not separate MCP servers. Preserve required
dispatch, memory/plan editing, writer and dispatcher dependencies.
