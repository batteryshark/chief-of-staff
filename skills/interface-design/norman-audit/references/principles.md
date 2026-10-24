# Principles — the DOET vocabulary, current as of 2026

The theory layer. Cite the Revised & Expanded edition of *The Design of
Everyday Things* (Norman, 2013), never the 1988 edition — the 1988 affordance
vocabulary is the part Norman himself retracted.

## Signifier, not affordance

- **Affordance** is a relationship: what actions are possible between an agent
  and a thing. It exists whether or not anyone perceives it.
- **Signifier** is the perceptible cue that communicates where and how to act.
  Signifiers are what designers control.
- Norman corrected the popular usage twice himself: "Affordance, Conventions
  and Design" (*interactions*, 1999) and "Signifiers, not affordances"
  (*interactions*, 2008 — "Forget affordances: provide signifiers").
- On screens nearly everything affords clicking, so the design question is
  always the signifier. Flat design's "false floor": the affordance survives,
  the signifier dies (NN/g, clickability signifiers:
  https://www.nngroup.com/articles/clickable-elements/).
- A **Norman door** (push plate that says PULL) is a signifier failure, not an
  affordance failure — the door opens fine.

**Audit rule:** for every possible action, name the perceptible signifier from
where the user stands. "It's tappable" is a failing defense.

## The two gulfs

Seven stages of action: goal → plan → specify → perform → perceive →
interpret → compare. The two gaps:

- **Gulf of execution** — the user cannot find or form the action that serves
  the intention. Fix with signifiers, conventions, constraints.
- **Gulf of evaluation** — the user cannot tell what the system did. Fix with
  feedback and visible state.

Classify every interface failure as one or the other before fixing it; the
fixes differ. (NN/g: "The Two UX Gulfs,"
https://www.nngroup.com/articles/two-ux-gulfs-evaluation-execution/.)
Treat the seven stages as a diagnostic checklist, not a literal theory of
cognition — Suchman's *Plans and Situated Actions* (1987) is the standing
academic critique.

## Conceptual models

Users act on a mental model built from what the interface shows (the system
image). Mistakes — as opposed to slips — come from wrong models. The interface
must let a first-time user predict what an action does before doing it.
(NN/g: https://www.nngroup.com/articles/user-mistakes/.)

## Mapping

Arrange controls in spatial correspondence with their effects (stove burners
are the canonical failure). Norman grounds "natural" mapping partly in
**cultural convention** — it is not universal; follow the target market's
convention when physical analogy runs out.

## Feedback

Every action gets a perceptible, timely, informative response; silence is a
defect. Modern refinement adds timing budgets (0.1s / 1s / 10s — see
interaction-cost.md) and skeleton/optimistic-UI patterns. This is Nielsen
heuristic #1, visibility of system status.

## Constraints

Physical, cultural, semantic, logical. In software: disabled states, input
masks, valid-range pickers, structured editors. Make the wrong action
impossible or hard **before** making the error message good (NN/g on slips:
https://www.nngroup.com/articles/slips/).

## Forcing functions

Interlock, lock-in, lock-out. Modern practice narrows their use: confirmations
habituate and get clicked through — prefer **undo** for anything reversible
(Nielsen heuristic #3). Reserve forcing functions for irreversible or
destructive acts, and make those confirmations specific (type the name, name
the consequence), never generic "Are you sure?".

## Slips vs mistakes

- **Slip**: right goal, wrong execution (typo, adjacent tap, habit capture).
  Fix with constraints, target size, spacing, undo.
- **Mistake**: wrong goal from a wrong model. Fix the system image: labels,
  feedback, visible state.
Diagnose which one you have before touching anything; they have disjoint cures.

## Knowledge in the world vs in the head

Behavior combines what the user remembers with what the interface shows. World
knowledge needs no learning but must be perceivable; head knowledge is fast but
costly to acquire and fragile under load. Design for both: visible for first
use, bypassable for the fluent (shortcuts, flags, muscle memory). Descendant:
recognition over recall, Nielsen heuristic #6
(https://www.nngroup.com/articles/recognition-and-recall/).

## What refined DOET since

- **Emotion**: Norman's own *Emotional Design* (2004) reversed the 1988
  omission; the **aesthetic-usability effect** is real and replicated (Kurosu &
  Kashimura 1995; Tractinsky 1997–2000; NN/g:
  https://www.nngroup.com/articles/aesthetic-usability-effect/): attractive
  interfaces buy tolerance for minor problems — and can mask issues in testing.
- **Heuristic evaluation**: Nielsen's 10 heuristics (1994; 2020 refresh,
  https://www.nngroup.com/articles/ten-usability-heuristics/) are DOET
  operationalized as an audit instrument, with the 0–4 severity scale
  (https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/).
- **Excise** (Cooper, *About Face*): work that does not move the user toward
  the goal — navigation, window management, confirmations, re-entry. The
  design goal is minimizing it. Sovereign apps (long sessions) feel excise
  worst.
- **Design systems** (HIG, Material, GOV.UK) ship these principles as
  pre-decided components; prefer the platform's solved pattern to a novel one
  (Jakob's law — users live in other people's interfaces).
- **WCAG 2.2 (2023)** turned several principles into testable floors:
  target size, redundant entry (never ask twice), consistent help, accessible
  authentication, focus not obscured
  (https://www.w3.org/WAI/standards-guidelines/wcag/).

## Folklore corrections (do not repeat the retellings)

1. "Affordance = visual cue" — the cue is the signifier; Norman corrected this
   twice (1999, 2008).
2. "Norman doors are bad affordances" — they are bad signifiers.
3. "Norman invented affordances" — Gibson did; Norman imported, then split it.
4. "Natural mappings are universal" — partly cultural, per Norman himself.
5. "DOET says aesthetics don't matter" — a 1988 omission, reversed by its own
   author; aesthetic-usability is replicated.
