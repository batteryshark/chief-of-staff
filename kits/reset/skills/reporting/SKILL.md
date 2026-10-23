---
name: reporting
description: Explicit owner-bound escalation and answer handling.
---
# Reporting and answers

## Opt-in native pilot

Use the native bus only when this exact origin is enabled; access is session-gated. Post with
`chief_post({urgency:"fyi",text,ref,key})` for a real status/milestone, or normal/urgent
for a genuine question. Ref and stable key are bounded, private, and per original origin;
reuse the same key/payload after an uncertain receipt, never invent another event.
For a genuine question supply optional `limits` with exact original scope/freshness/hands
limits (at most4000 characters); stable-key retries must preserve it verbatim. A legacy
FYI without this field remains valid. Missing limits are visibly missing, never invented.
Strategic and decision items go ONLY to the chief, including urgent/reserved needs.
The bus queues them in the chief inbox; it never converts origin prose into principal cards.
Only the chief sends principal decision cards with chief-nod ask. Ordinary messages and
alerts still use Nod. Historical card answers remain data, not effects or goal resume.
Real post routing, plain-ask Nod origin wake and reset's matching own-goal answer wait
are accepted; do not retest them. Keep plain inbox/fresh-pointer fallback until EACH
recipient's own real path works; never duplicate effects on both transports.

For a real event wait, post the question then use `chief_wait({event,lane:"reset"})`
only when no independent work/owned workers need you; end the turn after confirmed pause.
Normal dispatch allows enrollment before its four-minute due time; don't manufacture
urgency or treat a racing answer as permission to override a goal stop. An answered/closed
event cannot admit a new wait. An uncertain delivery needs reconciliation, not another send.
For time-only waits use the existing Docket timer/alarm (exact own session/directory),
then `chief_wait_time({item,lane:"reset"})` with its real one-shot ID; end the turn.
On its genuine admitted wake, explicitly `chief_resume_time({item})`. No model polling,
fake questions, recurring-item enrollment or arbitrary-wake auto-resume.
Wait tools only support the reviewed Goal and Stop conditions sections, not mutable status.
The app API has no CAS; exact own-wait/final rereads reject observed manual stops, not
every simultaneous UI race. Never alter the goal or holds merely to make a wait succeed.

Existing Docket check-ins stay on their scheduler/roster. Their prompt asks the lead to
report to the chief: handle that genuine request through this same reporting procedure.
No direct scheduler-to-bus hook or second eligibility scanner is installed.

For your OWN genuine accepted visible milestone, use installed `docket_milestone` with
only `milestone_at` (actual accepted timestamp with timezone) and `milestone_ref` (evidence).
Native caller identity must match your existing enrolled row; no owner/path/env selectors.
No direct roster read/edit grant, enrollment, state change or other-row access is supplied.
A confirmation time is not an invented earlier selection time. Log touches, messages,
mtimes and counters are not milestones. Unknown outcomes need owner inspection, no retry.
Unavailable/denied tool: report the exact gap; never use shell or broader file writes.
The helper preserves0700/0600/state/other rows and checks expected bytes under flock;
that is NOT CAS against arbitrary writers or an atomic fence against session moves.
See the configured Docket checkout's `LEAD_CHECKINS.md`; do not replay already
recorded milestones or treat text as certified acceptance.

Technical decisions stay with the lead. Escalate genuine scope/taste/reserved/hands
needs, cross-project conflicts and serious goal risk, not routine methods or status.
Use the existing plain chief inbox for quiet reports and targeted current-owner
messages for needed answers. Re-read the configured pointer before sending; never
use cached retired addresses or title-search substitutes. Do not send a principal
decision card from a lead session. Preserve the pending item if the chief route fails.

Give project, exact needed outcome, recommendation/default, why that owner is needed
and what continues or why nothing can. Silence never approves an effect.
Retain original session, absolute directory, stable private reference, scope and limits.
Apply only a matching answer. Ignore resolved duplicates; late receipts/PENDING cannot
reopen resolved waits. Receipt, delivery and observed completion are different facts.
Avoid automatic chief-conversation returns and acknowledgement loops. No routine FYIs
via targeted messages; preserve the quiet inbox route until real bus recipients work.
Set returnResult:false normally in both directions. Never guess, impersonate an owner
or silently switch targets. A receipt/PENDING is never a private answer or approval.
If transport is unavailable, retain the gap in LEAD.md and continue independent safe work.
Do not disguise a serious unreportable safety blocker; surface it to the principal.

Chief decision cards use short, plain technical English in ASD-STE100 style. The helper
checks structure, not full language certification: exactly one question marked with ?,
2–3 explicit options each with one-line description of its outcome, one recommended
option id, and a stated no-answer default. No review/discuss/read-this options. Both
input and rendered summary + body must fit600 Unicode characters, including generated
outcomes/recommendation/default. Use --dry-run before sending. Refusal has no outward
effects; edit the card yourself. No automatic shortening or added choices. A default is
displayed, never executed. Ordinary informational messages use nod-alert, not ask.

Current chief's scoped `chief_urgent_call` is the ordinary Voicestack CLI, not managed-call-v1.
Use only for a real decision/goal-risk under existing standing call permission. Input:
fresh operation_id UUID, reason decision|goal-risk, title<=100 and body<=1000 characters.
Native caller/pointer/message supply identity; no model-selected session, URL or token.
The backend/phone retain Calls, quiet-hours, pairing, outstanding-call and native-origin
checks. Speech preparation can take150s; the CLI then observes first phone receipt for
15s (a slow final status read may extend wall time). Intent/APNs is not ringing, answer
or media proof. Ordinary calls have no daily/spacing cap. No retry loops, same-ID replay,
new ID to evade uncertainty, or automatic follow-up notifications. After an unknown
outcome, inspect the existing operation through the owner's read-only status route.
No managed registration/reusable grant or cryptographic caller-isolation claim applies.
