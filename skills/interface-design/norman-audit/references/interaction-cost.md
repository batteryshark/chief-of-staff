# Interaction cost — what is countable, what is not

Read this before asserting any number. Evidence tiers: **[SCIENCE]** =
replicated result. **[HEURISTIC]** = evidence-informed rule of thumb.
**[FOLKLORE]** = debunked or unsupported as commonly stated; never cite as fact.

## The cost ledger [HEURISTIC, well-grounded]

Interaction cost is the sum of mental and physical effort to reach the goal
(NN/g: https://www.nngroup.com/articles/interaction-cost-definition/).
Components: reading; scrolling; looking around; comprehending; clicking or
touching; typing; page loads and waits; attention switches; memory load.

Mental costs usually dominate physical ones. There is no unit conversion
between a click and a memory item — minimize the total, never one component at
another's expense. Three mindless clicks beat one hard one (Krug).

## Counting rule (this family's contract)

Assert a number only when you can count it in source: taps, keystrokes,
screens, fields, flags, attention switches, items to remember. Otherwise stay
qualitative. The defensible pattern:

> "Flow X: 7 taps + 2 attention switches. The 3-tap alternative saves ~8s per
> run (KLM). At 20 runs/day that is a real tax."

Never: "7 clicks violates the 3-click rule."

## KLM — taps to seconds [SCIENCE]

Keystroke-Level Model (Card, Moran & Newell 1980/1983): expert, error-free
task time = sum of operators. K keystroke/tap ≈ 0.2–0.28s; P point ≈ 1.1s;
H home hands ≈ 0.4s; **M mental preparation ≈ 1.35s**; R system response.
Predictions land within ~10–20% of observed expert times; still used
(CogTool; validated touch extensions).

The M operator is the lever: each attention switch or decision point adds
~1.35s, which usually outweighs the tap it accompanies. Cutting a decision
beats cutting a tap.

Limits: models skilled execution only — not novices, errors, learning, or
satisfaction.

## Fitts's law and target sizes [SCIENCE]

Time to hit a target grows with distance, shrinks with size (Fitts 1954;
MacKenzie 1992; NN/g: https://www.nngroup.com/articles/fitts-law/). The most
replicated result in HCI.

Hard numbers to audit against:
- Apple HIG: **44×44 pt** minimum tap target.
- Material: **48×48 dp**.
- WCAG 2.5.8 (Level AA, WCAG 2.2): **24×24 CSS px** floor, with spacing
  exceptions; WCAG 2.5.5 (AAA): 44×44.
- Empirical thumb basis: ≥ ~9mm (Parhi/Karlson/Bederson, MobileHCI 2006).

Edge/corner "infinite width" applies to **cursor interfaces only**; touch gets
no edge bonus and edge targets can be slower (bezel overshoot). Fitts models
pointing, not decision time, visual search, or keyboard navigation.

## Hick's law [SCIENCE in the lab; FOLKLORE as used on menus]

Reaction time grows with log(n) — but only for known, practiced,
stimulus-response choices. Menu reality: novice menu use is **linear visual
search** (Cockburn/Gutwin/Greenberg, CHI 2007); log behavior appears only for
ordered/known sets (alphabetical bisection). CHI 2020 (Liu et al., "How
Relevant is Hick's Law for HCI?") warns the law is mostly misapplied — it does
not even support "fewer options is faster" for practiced users.

Rule: organize, group, and order options; don't just count them. Broad beats
deep for known sets. Do not cite Hick for unordered menu scanning, novel
choices, or reading-based decisions. The "decision fatigue" extension rests on
ego depletion, which failed preregistered replication (Hagger et al. 2016) —
do not cite it.

## Memory limits [SCIENCE — but not the number you think]

Working memory holds **4±1 chunks** (Cowan 2001), not 7±2. Miller's 7±2 was
about unidimensional judgments and immediate recall of chunks, and Miller
himself objected to the UI misuse. Visible menus and lists cost *scanning*,
not memory — recognition, not recall.

Rule: never require the user to carry more than ~3–4 items across screens or
steps (codes, comparisons, cross-page values). On-screen item counts are
governed by search and scent, not by 7.

## Response time [HEURISTIC, evidence-informed]

0.1s = feels instantaneous; 1s = flow of thought holds; 10s = attention limit,
needs progress (Nielsen 1993, from Miller 1968;
https://www.nngroup.com/articles/response-times-3-important-limits/). The
0.1s perception threshold is robust; 1s/10s are order-of-magnitude guides.
Print or render *something* within ~100ms.

The Doherty threshold (400ms) is a 1982 single-company mainframe report,
never replicated as a law — cite Nielsen's limits instead.

## Navigation: scent beats click count [SCIENCE]

The 3-click rule is debunked: 44 users, 620 tasks, no correlation between
click count and success or satisfaction (Porter/UIE 2003; NN/g concurs).
What predicts success is **information scent** (Pirolli & Card 1999): users
follow proximal cues and persist through many clicks while scent stays strong.
First-click correctness predicts task success (~87% success after a right
first click vs ~46% after a wrong one — Bailey & Wolfson).

Rule: optimize the scent of each step, not the count of steps — **except** in
high-frequency expert flows, where counts are KLM territory and every tap is
a recurring tax. Know which regime you are in before asserting either.

## Progressive disclosure [HEURISTIC]

Show the frequent few, defer the rest behind an obvious "more" (Nielsen 2006:
https://www.nngroup.com/articles/progressive-disclosure/). Two failure modes:
wrong frequency split (hiding what most users need), and an invisible "more".
Accordions raise interaction cost and hurt discoverability on desktop; most
users never change defaults, so hidden-by-default = unused-by-most.

## Step-counting methods with published standing

- **KLM/CogTool** — predictive, converts counts to seconds. [SCIENCE]
- **PURE** (Rohrer et al., CHI 2016) — experts rate each step's friction 1–3;
  correlates with usability-test metrics. [HEURISTIC]
- **Cognitive walkthrough** (Wharton et al. 1994) — per-step: will they know
  what to do, see the control, understand the feedback? [HEURISTIC]
- **First-click testing** — measurable success-rate deltas. [SCIENCE]

## Folklore blacklist (never assert as fact)

1. The 3-click rule (debunked; scent replaced it).
2. 7±2 for anything visible on screen (real WM limit ≈ 4±1, remembered items only).
3. Hick's law for unordered menus (linear search is the real model).
4. Doherty 400ms as a law (unreplicated; use 0.1/1/10s).
5. Decision fatigue (ego depletion failed replication).
6. "Fewer clicks = happier users" for navigation (scent, not count — but counts
   still matter in high-frequency expert flows).
