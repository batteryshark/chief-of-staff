---
name: norman
description: Apply interface-design principles while building any interface — screens, forms, flows, CLI commands, TUI views, error messages, empty states. Runs a five-question walkthrough on every surface: has it earned its place, can the user find it (name the signifier), what does it cost (count when countable), do they know it worked, does it survive first use, hundredth use, and interruption. Use when designing or changing an interface, when a flow feels circuitous, or when features keep going unfound. Not for pure visual styling, backend-only work, or prose that is not interface copy.
---

# Norman

Interface-design discipline named for the Norman door: the elegant pull handle
on a door that opens with a push. Software ships that door constantly — the
feature nobody finds, the form that asks what the system already knows, the
delete control beside rename. This skill catches those while you build.

## The walkthrough

Every surface you add or change — control, field, screen, flag, prompt, error,
empty state — answers five questions, in order:

1. **Has it earned its place?** Every control starts at minus 100 points and
   buys its way in. Before adding one, try to absorb the complexity instead: a
   default, an inference, a convention. Someone always pays for complexity;
   prefer it to be you, not every user on every visit.
2. **Can they find it?** Stand where the user stands when the need arises and
   name the perceptible signifier. Labels carry scent: the user's words, not
   your schema's. A capability with no signifier on the natural path does not
   exist — not even for its builder.
3. **What does it cost?** Count the primary path: taps, keystrokes, screens,
   attention switches, items held in memory. Numbers when countable, prose
   when not. The system holds state; the user never re-enters what it already
   knows.
4. **Do they know it worked?** Something visible within ~100ms. Current state
   readable on screen, never inferred. Undo over confirmation. Constrain the
   slip before polishing the error message. Errors state cause, then fix.
5. **Does it survive the walk?** Walk it twice: first use (does it teach
   itself?) and hundredth use (does it get out of the way?). Then leave
   mid-flow and come back: is the state still there, with a cue to resume?

## Rules

- One primary action per screen. Everything else is smaller, later, or gone.
- Recognition over recall: picker over format, completion over memorization,
  visible option over documented option.
- Visible state beats remembered state: mode, scope, and progress on screen,
  always.
- Errors: cause, then fix, in the user's language. No raw traces, no blame.
- Never manufacture urgency. Badges, timers, and red are reserved for things
  that are actually urgent.
- Accessibility minimums are floors, not trade-offs: target sizes, keyboard
  paths, focus visibility, reduced motion. Simplification never buys them back.
- Folklore ban: never cite the 3-click rule, 7±2 for on-screen items, Hick's
  law for menu scanning, "80% of users use 20% of features", decision fatigue,
  or 23-minutes-per-interruption. The references carry what replaced them.

## Deliberate corners

Mark a deliberate UX corner with a comment naming the ceiling and the upgrade
trigger: `norman: <ceiling>, <upgrade trigger>` — for example
`<!-- norman: no empty-state hint, add when someone misses the feature -->`.

Harvest the ledger any time with the bundled tool:

```
bin/norman [path] [--json] [--fail-on-no-trigger]
```

One row per marker; markers with no upgrade trigger are flagged — a corner
with no revisit condition is the one that rots.

## References

Load on demand, exactly when the situation names them:

- Read [references/principles.md](references/principles.md) when you need the
  core vocabulary defended — signifier vs affordance, the two gulfs, slips vs
  mistakes, constraints, forcing functions — or a citation for any of it.
- Read [references/interaction-cost.md](references/interaction-cost.md) before
  asserting any number: taps, target sizes, response times, memory limits. It
  separates measured from folklore.
- Read [references/cognition.md](references/cognition.md) when working on
  discoverability, state visibility, memory load, notifications, or
  interruption and resumption.
- Read [references/bloat.md](references/bloat.md) when arguing a control has or
  has not earned its place.
- Read [references/cli-tui.md](references/cli-tui.md) when the interface is a
  CLI or TUI.

To pressure-test a flow, run the
[first-time-user](agents/first-time-user.md) role prompt as a subagent against
the surface you just built.

If the workspace carries its own interface standard (a usability gate list, a
design system, an accessibility standard), read it and apply both. This skill
is the general layer, never a replacement for a house standard.

## When NOT to apply

Never sand off: expert efficiency (command-line and power tools trade a high
first-use cost for a near-zero hundredth-use cost, and that trade is often
correct); friction that is the point (deliberate confirmation of destructive
acts, game mechanics); legally or safety-required steps.

Aesthetics are not the enemy. Attractive interfaces measurably buy tolerance
(the aesthetic-usability effect); this skill governs function and findability,
not visual identity. Do not flatten a brand to save a border.

Never trade correctness for smoothness: an interface that guesses wrong
silently is worse than one that asks.

The best interface is the one the user does not remember using.
