## Local domain handoffs

Read `{{SERVICE_GUIDE}}` for shared-service ownership and limits.

If a domain directory is configured, resolve its live `chief.json` on every contact;
never cache sessions or title-search. The shared default directory is
`~/.config/chief-of-staff/domains.json`. Follow `{{DIRECTORY_GUIDE}}`
contract: attributed stable handoff id, origin/domain, owner and intended action;
use existing `a2a_send` for inter-chief handoffs, not `session.send`. Only the owner
writes its private memory. The technical receiver alone records technical ideas
in its own `ideas.md`, deduplicating the handoff id and returning a receipt through
the automatic reply, never a new-send acknowledgement. Unknown ownership gets one
clarification; timeout is unresolved, not permission for a new id or replay. No
handoff authorizes outbound contact, scheduling or service startup.
