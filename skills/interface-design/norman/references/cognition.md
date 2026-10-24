# Cognition — the interface as the user's memory

The science behind "the interface holds the state so the user doesn't have
to." Read when working on discoverability, state visibility, memory load,
notifications, or interruption and resumption.

## Distributed cognition [strong framework; offloading branch is SCIENCE]

Cognition spans people + artifacts + environment (Hutchins, *Cognition in the
Wild*, 1995; Hollan/Hutchins/Kirsh, TOCHI 2000). People arrange the world to
encode task state (Kirsh) and offload when internal demand exceeds capacity —
offloading improves performance, and lower-working-memory users offload more
(Risko & Gilbert, *TiCS* 2016 — cite this, not the "Google effect," which
failed replication).

The catch: offloaded content is remembered *worse* internally. An interface
that invites offloading and then drops the state delivers the worst of both
worlds — the user released their memory and the system lost the copy.

**Rule:** any state the system knows — selection, progress, prior inputs, what
exists — is represented on screen, never re-derived by the user.

## Interruption and resumption [SCIENCE]

Suspended goals decay (Altmann & Trafton, memory-for-goals, *Cognitive
Science* 2002). Resumption takes measurable lag and produces errors; it
depends on **associative cues present at the point of return**. Longer or more
demanding interruptions → worse resumption (Monk/Trafton/Boehm-Davis 2008).

**Rule:** after any interruption — tab switch, timeout, crash, navigation —
restore the exact prior state AND show a resumption cue: where you were, what
was in progress, what's next. Losing a draft, filter, scroll position, or
wizard step converts a seconds-scale resumption into full goal reconstruction.

W3C COGA ("Making Content Usable") states it as a requirement: users should
not need to rely on memory for information from previous steps.

Folklore flag: "23 minutes to recover from an interruption" is a press-quote
distortion of Mark et al. CHI 2005 (time to *return to* a work sphere, not
attention recovery). Use Altmann/Trafton for UI claims: resumption lags of
seconds, scaling with interruption length and demand.

## Discoverability — the orphaned-capability class

**A capability with no perceivable signifier at the user's current location
functionally does not exist for that user — including its own builder.**

Why users never find it on their own: the paradox of the active user
(Carroll & Rosson 1987) — people pursue current goals and never inventory
features. "Awareness of functionality" is a named learnability failure class
affecting novices and experts alike (Grossman et al., CHI 2009).

Quantified: hiding navigation behind a hamburger roughly halved discoverability
and raised task time (NN/g, 179 users, 2016:
https://www.nngroup.com/articles/hamburger-menus/); field reversals at
Facebook and zeebox agree (LukeW, "Obvious Always Wins").

**Audit method:** enumerate what the system can do (schema, API, routes,
commands). For each capability, walk from the default screens along the user's
natural paths. Anything no visible element leads to is an orphan. Progressive
disclosure is legitimate — the failure class is *zero* signifier on the
natural path, not "not everything on screen."

## Information scent [SCIENCE]

Users choose links by expected value estimated from proximal cues — the words
in the link (Pirolli & Card 1999, one of HCI's few quantitative theories).
Weak scent → abandonment at any click depth. Label wording dominates
structural elegance.

**Rule:** every navigational label contains the words the user would use for
the goal behind it. A capability filed under "Miscellaneous", internal jargon,
or a cute name is an orphan with extra steps.

## Status visibility [HEURISTIC with strong roots]

For each screen the user must be able to answer without memory or clicking
away: where am I, what is the system doing, what just happened, what happens
next. Save state, sync state, background jobs, current mode — readable, not
inferred. (Nielsen heuristic #1; Endsley's situation-awareness work says most
awareness errors are level 1: the data was never displayed.)

## Calm technology [design philosophy; attention cost is real]

Attention is the scarce resource (Weiser & Brown 1996; Case 2015). State the
user needs ambient awareness of belongs in persistent peripheral display —
badge, status strip, indicator — not in interruptive notifications. Every
notification is a self-inflicted interruption with a resumption cost (see
above). Reserve the center of attention for events that need action now.
Tension to manage: fully peripheral can mean invisible — check the
discoverability rules before calming something into nonexistence.

## The eight finding classes

1. **Orphaned capability** — exists in schema/API/code; no signifier on any
   natural path. *Detect:* diff system capabilities against per-screen
   signifiers.
2. **Scentless label** — linked, but the label shares no vocabulary with the
   user's goal. *Detect:* jargon, generic buckets, cute names.
3. **State amnesia** — interruption discards draft, filter, scroll, or step.
   *Detect:* leave mid-task, return; anything re-entered is a finding.
4. **Missing resumption cue** — state survives but the return screen looks
   like a fresh visit. *Detect:* no "where you were / what's next" marker.
5. **Recall-demanding input** — the user retypes or remembers what the system
   holds. *Detect:* any field answerable from existing data.
6. **Invisible status** — save/sync/job/mode state exists but is not shown.
   *Detect:* answering "is it saved? which mode?" requires memory or a probe.
7. **Center-stage abuse** — non-urgent, non-actionable events delivered as
   interruptions. *Detect:* notification whose only action is "dismiss."
8. **Offload-then-drop** — the UI invites externalization ("we'll remember
   this") then loses or hides it. *Detect:* trace every remembered artifact to
   where it resurfaces; no resurface point = finding.
