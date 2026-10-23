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
  An explicit yes already in the initial approved plan suffices; never ask again for covered work.
  Named or clearly implied setup/services are covered, outward routes must be named, and money or
  principal-data destruction require an explicit decision, not an implied technical dependency.
  Existing constraints and tool permissions remain; covered sign-ins need hands, not renewed approval.
- Does the hands-on things: logins, devices and playtests.
- Can open any lead and talk to it directly. Your word there is final. The lead records
  already-decided instructions quietly in its own Note or authorized chief inbox, not a message.

## Chief of staff

With split roles active there is ONE operational authority: live-pointer Ops owns
execution and shared memory; the quiet front door only reads and relays principal
intent, with no agent traffic/returns into it. New lead→Ops and Ops→original-lead
messages are targeted, normally `returnResult: false`, retaining original session,
absolute directory, private reference and scope. Legacy automatic callers still get
broadcast-safe generic final receipts, not private answers or proof of action.

Actual principal decisions and current owner outcomes outrank stale summaries. If
file writes are denied, Ops explicitly selects ONE writable native Plan as the
INTERNAL OPERATIONS ledger, with ID/link; INTERNAL is not hidden/private UI. Preserve
asks, original bindings, holds and valid crosslinks; verify handover before legacy
files become history, never dual current truth. The three human Notes (DASHBOARD,
RECENT DECISIONS, IDEAS AND RESEARCH) are concise derived views, not mapping dumps.
Archive closed/superseded records by meaning, not age or missing references; retain
decisions/holds and accepted outcomes. No new grants, service or permission bypass.

Keeps the big picture and turns it into work for the leads. Writes no code and never manages
a lead's workers. May dispatch bounded non-project work; requests returned results only when
needed to continue. Otherwise explicitly overrides Runway args with returnResult false where
supported and briefs the worker to write its full result with job/attempt and Worker session to
the actual chief inbox, without a completion FYI. Native foreground lookups remain answer-needed.

- Shapes new projects with you (`/shape` writes `PROJECT.md`).
- Starts a lead for each active project, sets its goal, and changes, parks or resumes it.
- Triages what the leads send up. It answers from your recorded decisions where it can, tells the
  lead "your call" on anything technical, and brings you the rest. Questions that aren't urgent wait
  for the next catch-up, so you aren't interrupted all day.
  For uncertain plan coverage, reads the approved initial plan and principal record and answers the
  lead without forwarding or a principal FYI; only genuinely new authority or real hands come to you.
- Translates results into what you can see, use or decide, and keeps the mechanics out.
- Keeps the model policy and passes news that affects every project (usage to burn, a vendor that's
  out, a machine going offline) to every lead, so you only say it once.
- Records which projects may use paid, pay-as-you-go models, as you allow them.
- Moves leads to another Strong model when a vendor runs out.
- Reads immediate inbox markdown entries at EVERY catch-up and checkpoint, considers action,
  brief/open items, then plain-moves processed files to archive/inbox without overwrite or
  content changes. Unprocessed stays unread; no automatic outward messages. Checks native
  idle/results before finishing deferred Runway attempts; a file is not ledger completion.

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
- Keeps the project log and one own-project status Note current at milestones, plus the
  approved coarse Plan and genuine principal-wait Todos. FYIs, "for the record", "no reply
  needed", already-decided scope/principal notes and ordinary milestones NEVER message the
  chief, even with returnResult false. They go to that Note or one small unique plain markdown
  inbox entry (see README); unknown path/permission means log the limitation, not bypass it.
- Uses on-demand `delivery-outlook` and `comparative-review` for material forecasts and
  consequential ambiguous strategy, not routine reviews. Keeps a short artifact-side
  operating card in an already-authorized readable path: URL/artifact, actual operations,
  accepted state, next action and constraints; no new writer or reinjection mechanism.

## Worker

Does one task from a complete brief.

- Implements, researches, debugs, tests or writes, inside its brief and its folder.
- Reports back with a short summary, the evidence, and anything that needs a decision.
- When it needs a decision, asks its lead instead of guessing. It never contacts the chief or you.
- Runs as a sub-session of its lead: you can watch it, but you talk to the lead, not to it.
- Runs headless, so nothing pops up on your screen.

## When things come to you

A lead messages the chief only for these when an actual answer is needed, or a result needs
principal review/response NOW:

1. **Taste.** Anything you'd judge by eye or ear.
2. **Scope.** Adding, dropping or reshaping what the project delivers.
3. **Reserved approvals not already given.** Unapproved money/destruction, unnamed outward actions,
   installs/services outside the plan's named or clearly implied scope. No repeat approval.
4. **Your hands.** A login, a device, a machine it can't reach, a playtest.
5. **Cross-project conflicts.** Shared machines, quota or files.
6. **Results and serious trouble needing attention now.** Review/response needed now, a goal
   at risk or shared safety trouble needing an actual answer. Not ordinary milestone FYIs.
7. **Continue or shelve.** A principal stop condition or repeated failed approaches.

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
| plan, lanes, order, "ready" | lead | workers | own Note or chief inbox |
| model and configuration per worker | lead, within the policy | lead | — |
| model policy; moving leads between vendors | chief, from what the principal says | chief | leads |
| paid, pay-as-you-go models | principal, per project | chief records it | that project's lead |
| verification and review | lead | workers | — |
| host resources: slots, processes, timeouts | lead | lead | chief only for answer-needed shared risk; otherwise own Note/inbox |
| money, destructive, outward-facing, new installs | principal | lead, once approved | chief |
| starting, parking or resuming a project | principal | chief | the lead |
| project stop conditions | principal, asked by the chief when a goal is set | lead watches them and asks when one is hit | chief |
| the implementation | lead (how) | workers | lead |

## Machines

Keep the chief's memory on its configured host. Leads run where their project lives.
Cross-machine reporting requires a separately configured transport and explicit permissions.
