# Existing lead overlays and native plans

V2 appends project lead permissions after global lead permissions. A legacy
project `edit * deny` therefore shadows the global native-plan edit grant.
Updating only the global agent does not repair such an installation.

For an explicitly reviewed, managed `.opencode/opencode.json`, use the normal
binding installer's narrow mode, first with `--dry-run`:

```sh
python3 -B scripts/install-role-binding.py /canonical/project \
  --native-plan-only --expected-sha256 REVIEWED_CONFIG_SHA256 --dry-run
```

This mode inserts only the same home-expanded
`/.config/openchamber/projects/*/plans/*.md` edit allow immediately after the
single leading edit deny. Every existing rule remains in order, so later custom
denials/asks and secret restrictions still win. Unknown restrictions that block
the grant require owner review, not moving the allow to the end. Missing or
ambiguous baselines and duplicate JSON keys are refused. No Knowledge lookup,
roster, session, prompt, model, worker, writer, plugin or fleet operation occurs.

The supplied digest is a drift guard, not proof of kit ownership. Establish
provenance from installation receipts and review the complete target first.
Retain a metadata-preserving preimage and record mode, owner, group, xattrs and
ACLs before approving apply. Review the dry-run hashes and candidate; only then
omit `--dry-run`. Apply preserves original JSON bytes except the one insertion,
uses a metadata-preserving same-directory copy and atomic replace, and refuses
hash/metadata drift. The installer does not create a durable rollback backup.
Rollback requires the recorded exact postimage and metadata still present,
the verified backup preimage, and the same guarded copy/replace/readback method;
never overwrite intervening changes. Do not run the fleet installer for this fix.

Changing project config may reload the Location and interrupt commands. Coordinate
an owner-approved window and notify the active lead after apply. Explicitly inspect
interrupted commands and decide whether to rerun them; never automatically replay
operations.

V2 FileAccess uses absolute resources for external files, including native plans
outside the Location and project worktree. Historical Location-relative aliases
are not evidence that new external grants need aliases. Keep the absolute grant
for this external-plan case; do not add speculative relative or external-directory
permissions. A Location/worktree containing the native store is a different
normalization case and requires its own evidence and review.

Generated-rule tests are not native proof. After reviewed installation, the owner
reads the effective lead rules and resumes its original failed real lead plan
tick. A remaining denial is evidence to inspect, not permission to widen scope.
