# Lead own-project write scope

The generated global lead role allows only Location-relative `LEAD.md`,
`PROJECT.md`, and `lead/*` over its default edit denial. In V2, `*` includes
slashes, so the latter covers nested detail files. No roster, project enumeration,
or project config is needed for these internal files in a brand-new directory.
Do not restore `*/LEAD.md` or `*/lead/*`: those also match foreign paths.
Secrets denials remain last. Writer generation belongs to Galley; dispatcher
remains resolve-only. Shared edit action metadata must not become a tool-wide
edit denial in the role-context compiler.

## Native Plans: existing native Knowledge route

Use the lead's existing `openchamber_knowledge` tool with no `directory` or
`projectId` selector. List the session's default project, create/list its Plan,
then read its returned path and save that Plan by returned ID with `expected`
equal to its exact persisted prior body, not an assumed echo of the creation input.
For a checkbox update, change only that checkbox and preserve every other byte,
including constraints. A stale expected body must not be retried blindly.
This route needs no new permissions, plugin, enrollment or physical-plan binding.

An installed-host check verified this route using a fresh, never-bound lead in a
new directory, without a goal. Native list was initially empty; create/list returned
the new Plan; expected-CAS save returned progress 1/1. Native readback preserved
constraints and all text except the checkbox. Creation normalized away the trailing
newline: the first CAS using creation input was correctly rejected; reading the
persisted body before one corrected save passed. No directory/project selectors,
new permission grants or runtime plugin were used. The fixture finished idle.
This proves the own-default Plan route, not foreign-selector isolation.

This is authorized own-default Plan use, not a new foreign-selector privilege.
The schema also accepts explicit project/directory selectors; success on the
default route does not prove foreign-selector isolation. Native Knowledge writes
are not governed by the file tool's `edit` path rules.

## Optional direct Plan file binding

Native Plans live outside the session Location. Static relative role rules cannot
identify the caller's OpenChamber project ID or a newly created Plan. Do not allow
all projects' plan roots. If direct file-tool editing is needed instead:

1. Create/list the Plan through project Knowledge under owner authority.
2. In an integration window, run `scripts/install-role-binding.py LOCATION
   --dry-run` with the existing trusted harness credentials. Its Knowledge lookup
   obtains exact plan paths, independently of any model-supplied path manifest.
3. Review then apply that same installer, which changes only the project's
   permission config (plus its existing shell-wrapper policy). It does not enroll
   or mutate sessions, models, goals, or roster rows.
4. The lead can read/edit the exact listed Plan with native file tools. A Plan
   created later needs another discovery/binding pass; this is not automatic.

Do not add a broad Knowledge authorization shortcut to enforce own-project-only
access: there is no demonstrated own-caller-only enforcement for foreign selectors.
That limitation does not deny authorized own-default Plan use. No wildcard allow,
new action ID, permission override hook, or removed plan-edit shim is added here.

## Authoritative contract and installed check

Verified against https://opencode.ai/v2/docs/permissions and the public V2
OpenAPI at https://opencode.ai/v2/openapi.json: internal edit resources are
normalized Location-relative paths; external paths are canonical absolute;
rules are ordered, last match wins; edit/write/patch share `edit`. The plugin
guide documents transforms and permission evaluation, but no static
own-OpenChamber-plan variable. Public API is not installed-runtime proof.

The installed check added exactly the three relative grants while preserving all
57 existing rules and every other header/body byte, after all four affected leads
were confirmed idle. A fresh, never-bound lead then patched root LEAD.md,
root PROJECT.md and a nested lead detail file. Native readbacks confirmed the
contents. Separate source, secret and external-sibling mutation attempts were
denied without permission prompts; no denied file was created. The fixture ended
idle. The no-selector native Plan check above was also accepted; no per-project
permission config was needed for that route. These are bounded checks, not proof
of every path combination or foreign Knowledge-selector isolation.

For later installations, snapshot managed files, modes and native permission
layers, coordinate an idle integration window, and preserve unrelated changes.
Do not use active project files as probes. If a native check requires a visible
prompt, stop for approval.

Rollback: restore only snapshotted files whose hashes still equal this integration's
outputs (or remove a newly created config only if unchanged); restore original
mode. Never overwrite independent changes or revert native product state blindly.
The automated source tests alone do not establish installed-runtime behavior;
the bounded installed observations above were reported separately.
