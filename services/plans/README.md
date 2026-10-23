# Retired checkbox shim — historical contract

The separate checkbox.mjs shim is retired and is not shipped or activated by this
kit. Normal Plan access uses exact project-owned Knowledge-discovered plan bindings
through the role contract; no roster or arbitrary-project edit grant follows.
The description below records the retired helper's containment contract, not an
available tool or installation instruction.

`plan_checkbox` was a scoped tool, separately installed with a trusted
session/agent/Location and fixed plan-ID→path binding from scoped Knowledge list.
No generic file permission, Knowledge save grant, service or shell selector.
Native permission `plan_checkbox:own` is asserted; fresh native session identity,
Location and archive state are checked. Archived/moved/foreign callers refuse.

Read the owned plan, then provide its allowlisted `plan_id`, one-based
`line_number`, exact `expected_line` without newline, and boolean `checked`.
Only a unique `- [ ]`, `- [x]` or `- [X]` line under the single `## Steps` section
can change. This changes only the checkbox byte. Duplicate lines, stale text,
fenced content, other sections and other fields refuse. No automatic retry;
`unknown` means the owner must inspect the existing plan. Genuine acceptance is
still the lead's responsibility. The tool cannot split steps or revise constraints.

The fixed canonical path and installed parent device/inode are checked on each
invocation. Current file inode/metadata are checked at lstat, no-follow open,
read and final reread. Inodes may change through legitimate atomic plan updates;
the file inode is freshly checked, not frozen forever to installation. No model
path or case variant is accepted. realpath must equal the configured path, symlink
ancestors/files and hardlinks refuse, owner and mode600/644 are required, parent
must be owned and not group/world-writable. Case aliases cannot select another
file; this is tool containment, not universal file-tool or shell isolation.

Only one call per plan per plugin instance proceeds. A fixed `/bin/cp -p` with
empty environment preserves mode/ACL/xattrs into a private temporary directory,
then the new bytes are fsynced and atomically renamed after the final byte/inode
check. Directory fsync follows. Unknown rename/fsync outcomes are never retried.
Other bytes, BOM/newlines and project metadata stay unchanged.

The final check/rename interval is NOT CAS against arbitrary writers, nor is the
fresh native read atomic with a session move. Parent/source swaps by another
same-UID process remain trusted-execution risks; no cryptographic isolation claim.
Whole-plan file tools remain denied under their existing rules. General run and
file-identity gates stay unchanged. Static ownership is trusted integrator config,
not model-supplied snapshot authority. Real use is not proven by registration.
