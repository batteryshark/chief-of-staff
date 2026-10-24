---
name: norman-audit
description: Audit an interface for design failures, from source alone — a changed diff or a whole workspace. Hunts eight failure classes (controls that never earned their place, orphaned capabilities, scentless labels, excise steps, recall demands, mute actions, slip traps, state amnesia) across screens, forms, navigation, CLI commands, and error messages, and returns ranked one-line findings with fixes, citing file and line. Use to audit an interface or UX, review an interface change, find out why users cannot find features, or decide what a UI should drop. Reports only; does not apply fixes. Not for code quality, correctness, or security review.
---

# Norman audit

Audit the interface the way its schema cannot see it: from where the user
stands. Scope: the diff under review when one is given, otherwise every
surface the workspace ships.

## Anchor

Name the product's 3 most frequent user tasks (from README, docs, or
inference — say which). Walk each task's path first and count its steps.
Findings on those paths outrank findings elsewhere at equal severity.

## Tags and severity

- `cut:` control or feature that never earned its place. Fix: nothing, a
  default, or the system absorbing it.
- `orphan:` capability with no signifier on the user's natural path. Fix: put
  the signifier where the intention forms.
- `scentless:` label sharing no vocabulary with the user's goal. Fix: the
  user's words.
- `excise:` steps that do not advance the goal. Fix: the shorter path,
  counted (N → M).
- `recall:` the user must remember or re-enter what the system knows. Fix:
  prefill, show, or pick.
- `mute:` action without feedback, or state without display. Fix: the visible
  response or status.
- `trap:` slip waiting to happen — unconstrained input, destructive act
  without undo, a signifier that lies. Fix: the constraint, the undo, the
  honest cue.
- `amnesia:` state lost across interruption or navigation; no resumption cue.
  Fix: persist it, and mark where the user left off.

Severity — **higher number = worse, always list S4 first**: S4 catastrophe
(blocks or destroys), S3 major (fails often, hard to recover), S2 minor
(recurring friction), S1 cosmetic. Rated on frequency × impact × persistence.
S-numbers are not priority ranks; do not invert them.

## Hunt

- Diff capabilities against signifiers: everything the schema, API, routes,
  and commands can do, minus everything a screen, menu, or help text points
  at. The remainder is orphans — read
  [references/cognition.md](references/cognition.md) for the method and the
  eight finding classes.
- Forms: field counts, required attributes, fields answerable from existing
  data.
- Labels and copy: internal names leaking into UI strings; error messages
  without cause and fix.
- Mutations without a visible response; state (mode, save, sync, scope) that
  exists but never renders.
- Destructive paths: confirmation, undo, dry-run, adjacency to safe controls.
- Drafts, filters, and progress across navigation: persisted? resumption cue?
- CLI/TUI surfaces: run the 12 mechanical checks in
  [references/cli-tui.md](references/cli-tui.md).
- House standard: if the workspace carries its own interface standard, audit
  against it too and cite it per finding — it outranks this skill where they
  disagree.

Start with the bundled evidence collector; it reports facts, never verdicts:

```
bin/norman-audit [path] [--json] [--section forms|targets|flags|state]
```

Count what source lets you count (taps, fields, flags, steps, px) — read
[references/interaction-cost.md](references/interaction-cost.md) before
asserting any number. A claim that needs the running product (timing,
rendering, actual focus order) is labeled `needs live check`, not asserted.
To adversarially verify a finding before reporting it, run the
[skeptic](agents/skeptic.md) role prompt as a subagent.

## Output

One line per finding, ranked worst first — S4, then S3, S2, S1 — ties broken
by user cost. Format: `S<severity> <tag> <what>. <fix>. [<file>:<line>]`.
End with: `net: -<N> controls, -<M> steps, +<K> signifiers needed.`
Nothing to flag: `No Norman doors. Ship.`

## References

- [references/principles.md](references/principles.md) — the DOET vocabulary,
  current: signifiers, gulfs, slips vs mistakes, constraints.
- [references/interaction-cost.md](references/interaction-cost.md) — what is
  countable; the folklore blacklist.
- [references/cognition.md](references/cognition.md) — discoverability,
  memory, interruption; the eight finding classes.
- [references/bloat.md](references/bloat.md) — the earn-its-place evidence and
  severity practice.
- [references/cli-tui.md](references/cli-tui.md) — the 12 mechanical CLI/TUI
  checks.

## Boundaries

Interface design only. Code quality, correctness, and security go to their
own review passes. Accessibility minimums are floors, never findings to
"simplify away." Reads source, changes nothing, one-shot.
