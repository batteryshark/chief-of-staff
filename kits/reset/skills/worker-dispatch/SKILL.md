---
name: worker-dispatch
description: Start or continue bounded chief/lead work with quota routing and nested workers.
---
# Worker dispatch

Read current ~/.chief-of-staff/models.md, project permissions and Runway usage before new work.
Use the operator-authorized providers and routes; no private account/model preference is supplied.
Choose capability, then observed usage/reset. Spend expiring allowances on useful authorized
work, never invent jobs or capacity, buy credits or redeem resets.
Reuse the kit's routing/WORKFLOW.md for prepare, dispatch, bind and reconcile/finish.
A refusal is not permission to evade quota, permissions or writer isolation. Use the documented
manual fallback only after resolving the reason and recording the authorized exception.

## Selectable model aliases

Search native model aliases with `all:true`; preserve the returned selectable ID.
Fast/Ultrafast share the existing OpenAI pool/windows/cap, not extra capacity.
Honor Runway `unavailable_transports` markers: the current OpenChamber create/send
validator requires the ID repair before these routes can be admitted. Nested
creation alone does not repair the later session.send call. Do not normalize an
alias to underlying `modelID` or improvise a transport to bypass admission.
Parent-model inheritance is not per-worker selection proof. Require exact selected
provider/model/variant readback for any enabled picker-offered model once repaired.

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

Brief outcome, completion criteria, project/checkout paths, authority/holds, protected resources,
relevant failures, proportionate checks, changed paths, uncertainty and pending commands/effects.
Include the two-try rule and 30–45 minute simplest-route checkpoint, plus:
“Stay in this project folder; don't move this session into a worktree unless I ask.”
End with the actual parent's question route:
“If you need a decision or information, don't guess and don't use the built-in question prompt.
Send your question to session <parent> with openchamber session.send, returnResult true,
then continue with its answer. If PENDING, end your turn; the answer arrives later.”

Answer worker questions yourself; escalate only genuinely new authority or chief/principal choices.
Relay later answers to the original worker. Check actual results/state/effects before finish;
ambiguous creation is uncertain, not unsent. Never replay effects blindly. Wait by ending the
turn, not sleeping/polling. Keep running work intact until a safe checkpoint, then recover
the same job with its objective, paths, changes and pending effects preserved.

## Chief actions

Start persistent project-root leads with the approved whole goal/handover, lead agent and goal
mode, without automatic returns into the conversation. Restart an unchanged stopped goal with
the supported goal restart and Goal: plus its full objective; never bypass a hold.
Only the chief starts, re-goals or parks leads. Dispatch may restart an unchanged stalled goal
under standing authority, never parked/twice-rejected work. For work belonging to no project,
the chief may dispatch a bounded worker through Runway; request a return only if needed to
continue, otherwise use the quiet reporting route. Do not manage an existing lead's workers.
Archive sessions; never delete a parent or its children.
