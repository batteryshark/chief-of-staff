{{MARKER}}

# Chief of staff: startup note

This folder is the chief of staff's working memory. The conversation is not the memory: these files
are. A brand-new chief session that reads only these files must be able to carry on exactly where
the last one stopped.

**At the start of a session, after any compaction, and whenever you're unsure what's open, read
these before you answer:**

1. `brief.md`: priorities, one line per project, recent principal decisions, parked work.
2. `open.md`: every question waiting on the principal and every promise you've made.
3. `principal.md`: how the principal works, their standing permissions, and what to bring them.

Read these when needed:

- `models.md`: the model policy.
- `chief.json`: this chief's session id. Leads read it before they escalate, so keep it current.
- Each project's `LEAD.md` (paths are in the brief): that project's detail, owned by its lead.
  Don't copy project detail here.
- `archive/`: closed items, older decisions and earlier briefs.
- `chief-portfolio`, from the shell: one compact table of every project's status and what it's
  waiting on.
- The `checkpoint` skill (`/checkpoint`, or `/checkpoint fresh` to hand over to a new session): a
  sweep that makes these files a complete record. Run it when the conversation gets long.

**Write first, talk second.** Any decision, escalation or promise goes into these files in the same
turn, before you reply. An item in `open.md` closes only once it has been passed on. This file is
installed by chief-of-staff/install.sh; don't edit it.
