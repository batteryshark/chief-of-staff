---
name: worker-dispatch
description: Start or continue bounded chief/lead work with quota routing and nested workers.
---
# Worker dispatch

Read current ~/.chief-of-staff/models.md, project permissions and Runway usage before new work.
Use the operator-authorized providers and routes; no private account/model preference is supplied.
Choose capability, then usage/reset; spend expiring allowances only on authorized work, never buy credits or redeem resets.
Reuse the kit's routing/WORKFLOW.md for prepare, dispatch, bind and reconcile/finish.
A refusal cannot bypass quota, permissions or writer isolation; resolve its reason and record authorized manual exceptions.

## Selectable model aliases

Search model aliases with `all:true`; preserve selectable ID and variant, not the underlying modelID.
Honor Runway `unavailable_transports`; catalog visibility alone does not clear a transport block.
Fast/Ultrafast share existing OpenAI capacity. Inheritance is not explicit model selection.
Use high effort for design/diagnosis, medium for building/checking within authorized routes.

## Lead workers

Replace admitted session.create with a2a_create on local, using the selected model and agent.
Omit directory/nest overrides so the worker is nested under its lead in the project folder.
Then session.send to that exact session with model, variant, messageId, returnResult:true
and the complete brief. Bind after confirmed creation; results/questions return to the lead.
Native session cwd stays project root; parallel repository writers get separate registered
worktrees inside the project and an explicit Runway checkout. Tool paths use that checkout.
Load reset-worktree-safety before creating it; never move sessions unless the principal asks.
Use headless/offscreen work, cap heavy jobs and bound process creation. Stop only positively
identified owned runaway jobs, never broad pattern kills; report shared-host safety trouble.
Change a running worker's route/scope only at a safe checkpoint, not by killing its work.

Use an approximately 15-line brief, replacing placeholders with the actual assignment:
1. Outcome and completion criteria.
2. Project folder; assigned source checkout (tools use this checkout).
3. Owned paths and other owners' protected paths.
4. Existing decisions, holds and relevant failed approaches.
5. Decide, log and move within this authority; never bypass permissions.
6. Delegate denied project edits to an authorized worker through the parent.
7. Reversible own-setup work: relevant existing tests.
8. Shared live changes: one actual check and a rollback path.
9. Public, destructive or money effects: applicable approval required.
10. Heavy verification once at milestone end, not each step.
11. High effort for design/diagnosis; medium for building/checking.
12. After two failures change approach; after 30–45 minutes reassess the simplest route.
13. Stay in the project folder; do not move the session unless asked.
14. Report usable now / left first, then changed paths, checks and pending effects.
15. Questions/results: session.send to <parent>, returnResult:true; if pending, end the turn.

Answer worker questions yourself; escalate only genuinely new authority or chief/principal choices.
Relay answers to the original worker; reconcile results and pending effects before finish.
Ambiguous creation is uncertain, not unsent; never blindly replay it. End turns rather than poll.
Recover checkpointed work with its objective, paths, changes and pending effects preserved.

## Chief actions

Start project-root leads with the whole approved goal/handover, lead agent and goal mode, without automatic returns.
Restart unchanged stopped goals with supported restart and Goal: plus the full objective; never bypass a hold.
Only the chief starts, re-goals or parks leads. Dispatch may restart an unchanged stalled goal
under standing authority, never parked/twice-rejected work. For work belonging to no project,
the chief may dispatch through Runway; request returns only when needed, otherwise report quietly. Do not manage a lead's workers.
Archive sessions; never delete a parent or its children.
