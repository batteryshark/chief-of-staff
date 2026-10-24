# Bloat — why every control must earn its place

The economics of interface surface area. Read when arguing a control has or
has not earned its place.

## The evidence that features have carrying costs

**Feature fatigue** (Thompson, Hamilton & Rust, *J. Marketing Research* 2005;
HBR 2006 — the empirical anchor): before use, people choose capability over
usability, even knowing the cost; after use, the weighting **reverses** and
usability dominates satisfaction. The feature count that maximizes initial
sales exceeds the count that maximizes long-term satisfaction and repurchase.
Feature-loaded products sell, then erode.

**Featuritis** (Norman, DOET 2013 ch. 6): "creeping featurism is a disease,
fatal if not treated promptly." His cost model: "Complexity probably increases
as the square of the features: double the number of features, quadruple the
complexity." Causes he names: competitive pressure, existing-user requests,
the need to look new. Kathy Sierra's featuritis curve (2005) shows the same
shape from the user side: happiness rises to a peak, then falls as complexity
dominates — while pre-use buyers keep rewarding checklists.

**The per-visit tax** (Krug, *Don't Make Me Think*): users scan, satisfice,
and muddle through; a screen is a billboard with a fixed scan budget. Every
visible control competes for it on every visit, whether or not it is ever
used. Each element that requires thought draws down a finite reservoir of
goodwill.

## The decision procedure

**Minus 100 points** (Gunnerson 2004): every candidate feature starts at −100
and must buy its way in, because features are forever and compose
combinatorially.

**Tesler's law** (conservation of complexity): each task has irreducible
complexity; the only question is who absorbs it — the user, the application,
or the platform. An engineer-week spent absorbing complexity beats a
user-minute paid daily by everyone. Two corollaries:

1. Before adding a control, try to absorb it: a default, an inference, a
   convention. (Most users never change defaults — a good default is a
   control deleted.)
2. Do not simplify past the irreducible floor — removing needed control just
   ships the complexity back to the user as workarounds. Tesler is not a
   license to strip; it is an assignment of who pays.

**Reduction methods** (Maeda, *Laws of Simplicity*): Shrink, Hide, Embody —
in that order of honesty. Hiding moves the tax off the default view; it does
not remove it (and see cognition.md: hidden = undiscoverable when the hide is
total). "Simplicity is about subtracting the obvious and adding the
meaningful."

**Do less** (GOV.UK principle 2) and **one thing per page** (GDS 2015;
codified in the GOV.UK Design System "question pages" pattern). Published
result: Just Eat's checkout split into one-thing-per-page measured a
conversion lift of roughly 2 million extra orders/year (Silver, Smashing
Magazine 2017) — the best single evidence citation for the pattern.

## Severity and ranking practice

Heuristic-evaluation findings carry NN/g severity 0–4 (0 not a problem,
1 cosmetic, 2 minor, 3 major, 4 catastrophe), rated on frequency × impact ×
persistence
(https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/).
Nielsen heuristic #8 (aesthetic and minimalist design) is the bloat heuristic:
every extra unit of information competes with the relevant units.

## Folklore corrections

- **"80% of users use 20% of features" — do not cite as fact.** It traces to
  a Standish Group conference keynote (XP2002) about four internal apps,
  never published with methodology (debunk: Cohn,
  mountaingoatsoftware.com/blog/are-64-of-features-really-rarely-or-never-used;
  Bossavit, *Leprechauns of Software Engineering*). The defensible claim:
  feature usage is heavy-tailed — Microsoft's Office 2003 telemetry showed
  five commands (Paste, Save, Copy, Undo, Bold) dominating use with a barely
  touched long tail (Jensen Harris's Office UI archive). Say "usage is
  heavy-tailed," never a fake percentage.
- Rams's "as little design as possible" and Maeda's laws are touchstones, not
  evidence; cite feature fatigue for evidence.

## The combined argument, one paragraph

Visible controls are not free inventory. Each is a per-visit attention tax on
every user (Krug), the tax compounds super-linearly (Norman), buyers reward
adding it anyway (feature fatigue — which is why the pressure never stops),
and the honest alternatives are: absorb the complexity into a default or
convention (Tesler), subtract it (Maeda, GOV.UK), or make it earn its −100
back (Gunnerson). An interface earns calm by what it refuses to show.
