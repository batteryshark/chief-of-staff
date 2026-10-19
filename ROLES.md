# Roles

Who does what in the setup, from the principal down to the workers. The chain is
**principal ↔ chief ↔ leads ↔ workers**. Each level handles what it can and passes up only what it
can't decide.

## At a glance

| | principal | chief of staff | lead | worker |
|---|---|---|---|---|
| how many | one (you) | one, for every project and machine | one per active project | as many as the work needs |
| owns | the direction | the portfolio | getting one project done | one task |
| talks to | the chief; any lead, by dropping in | the principal and the leads | the chief and its workers | its lead |
| keeps | nothing; the others write it down | `~/.chief-of-staff` (brief, open items, principal notes, model policy) | the project log, `LEAD.md`, at the project root | the project files its brief covers |
| model | — | Strong class, any vendor with usage | Strong class, any vendor with usage | the class its job needs |
| runs | — | conversation, voice first | goal mode, until the goal is verifiably done | until its task is done |

## Principal

Sets the direction, and does the few things only a person can do.

- Decides taste (how things look, sound, read and feel), what each project should deliver, and
  what comes first across projects.
- Holds the reserved approvals: money beyond normal model use, destructive actions, anything
  outward-facing, and installs or downloads not already allowed for that project.
- Does the hands-on things: logins, devices and playtests.
- Can open any lead and talk to it directly. Your word there is final, and the lead tells the
  chief what changed.

## Chief of staff

Keeps the big picture and turns it into work for the leads. Writes no code and never manages
workers.

- Shapes new projects with you (`/shape` writes `PROJECT.md`).
- Starts a lead for each active project, sets its goal, and changes, parks or resumes it.
- Triages what the leads send up. It answers from your recorded decisions where it can, tells the
  lead "your call" on anything technical, and brings you the rest. Questions that aren't urgent wait
  for the next catch-up, so you aren't interrupted all day.
- Translates results into what you can see, use or decide, and keeps the mechanics out.
- Keeps the model policy and passes news that affects every project (usage to burn, a vendor that's
  out, a machine going offline) to every lead, so you only say it once.
- Records which projects may use paid, pay-as-you-go models, as you allow them.
- Moves leads to another Strong model when a vendor runs out.

## Lead

Owns one project's execution, from plan to verified result. Plans and checks, but doesn't
implement: apart from small read-only checks, the work goes to workers.

- Plans the work, splits it into lanes, sets the order, and decides when something is ready.
- Picks the model and configuration for each worker with `runway`: the class the job needs, then
  the vendor with usage left, spending allowances that would otherwise expire first.
- Dispatches workers with complete briefs, answers their questions, and verifies what comes back.
  It puts an independent reviewer on risky work, and sends wrong or incomplete work back.
- Manages the host's resources: caps on heavy jobs, concurrency, timeouts, and stopping its own
  runaway processes.
- Retries, reverts or reroutes work that failed, and logs each approach that didn't work. When
  your stop condition is hit or a problem keeps failing, it pauses that lane and asks you, through
  the chief, whether to keep going, change approach or park.
- Makes every technical decision inside the agreed scope, and logs it in one line.
- Keeps the project log current, and reports milestones to the chief in a headline and a few
  bullets. In OpenChamber it also keeps a short plan and your waiting items in the project's
  Project knowledge panel.

## Worker

Does one task from a complete brief.

- Implements, researches, debugs, tests or writes, inside its brief and its folder.
- Reports back with a short summary, the evidence, and anything that needs a decision.
- When it needs a decision, asks its lead instead of guessing. It never contacts the chief or you.
- Runs as a sub-session of its lead: you can watch it, but you talk to the lead, not to it.
- Runs headless, so nothing pops up on your screen.

## When things come to you

A lead escalates to the chief only for these:

1. **Taste.** Anything you'd judge by eye or ear.
2. **Scope.** Adding, dropping or reshaping what the project delivers.
3. **Reserved approvals.** Money, destructive actions, anything outward-facing, new installs.
4. **Your hands.** A login, a device, a machine it can't reach, a playtest.
5. **Cross-project conflicts.** Shared machines, quota or files.
6. **Milestones and serious trouble.** Something you can now see or use, or a goal at risk.

It never escalates verification methods, processes, job slots, merge order, model swaps within the
policy, test counts, file paths, worker routing, or disagreements between workers.

A question that reaches you comes as an outcome, with the options, a recommendation, and the
default that applies if you don't answer. The lead keeps working on everything else meanwhile.

## Who decides what

| decision | decides | carries it out | told |
|---|---|---|---|
| which projects run, and what comes first | principal | chief | leads |
| what a project delivers (goal, scope) | principal | chief writes the goal, lead plans against it | — |
| taste | principal | lead brings options through the chief | — |
| plan, lanes, order, "ready" | lead | workers | chief (by milestone) |
| model and configuration per worker | lead, within the policy | lead | — |
| model policy; moving leads between vendors | chief, from what the principal says | chief | leads |
| paid, pay-as-you-go models | principal, per project | chief records it | that project's lead |
| verification and review | lead | workers | — |
| host resources: slots, processes, timeouts | lead | lead | chief, only if other projects are affected |
| money, destructive, outward-facing, new installs | principal | lead, once approved | chief |
| starting, parking or resuming a project | principal | chief | the lead |
| project stop conditions | principal, asked by the chief when a goal is set | lead watches them and asks when one is hit | chief |
| the implementation | lead (how) | workers | lead |

## Machines

Keep the chief's memory on its configured host. Leads run where their project lives.
Cross-machine reporting requires a separately configured transport and explicit permissions.
