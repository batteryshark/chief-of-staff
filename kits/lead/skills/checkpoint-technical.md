# Checkpoint

Make your files a complete, trustworthy record of where things stand, so that compaction or a
fresh session loses nothing. Run it when the principal asks (`/checkpoint`), before you hand over to
a fresh session, and on your own when your conversation is getting very long. Compaction itself
comes without warning, so this doesn't replace writing things down as they happen. It's the sweep
that catches what slipped through.

If the arguments include `fresh`, finish the checkpoint and then hand over to a fresh session (see
Fresh session below).

## Your files

- **The chief of staff:** everything in `{{BRIEF_DIR}}`: `brief.md`, `open.md`, `principal.md`,
  `models.md`, `chief.json` and `archive/`.
- **A lead:** your project's `LEAD.md` and the `lead/` folder next to it.

## Steps

1. **Sweep.** Go back through the conversation since the last checkpoint (if you can't tell, use
   everything you can still see). Find what should be in the files but isn't:
   - the principal's decisions and anything they stated as lasting
   - questions waiting on the principal, and answers that came back
   - promises you made, and ones you've kept
   - things you passed on, status changes and milestones
   - approaches that failed, and stop conditions set or hit
   - findings about models

   Check each one against the files and write in what's missing. Leave out conversation detail
   nobody will need later.
2. **Tidy.**
   - **Chief:**
     - Close answered items in `open.md`, but only once the answer has been passed on, and move
       each to `archive/open-YYYY-MM.md` with its outcome.
     - Keep about twenty decisions in `brief.md` and move older ones to
       `archive/decisions-YYYY-MM.md`.
     - Run `chief-portfolio` and make every project row in the brief match its lead's log: the
       lead session, where it stands, what's next and the log's path.
     - Every active project has a stop condition line, and every Parked line a resume trigger and
       first step.
     - Add anything lasting the principal said to `principal.md`.
     - Confirm that `chief.json` holds your own session id (`echo $OPENCODE_SESSION_ID`).
   - **Lead:**
     - Status is current and ten lines at most.
     - "Waiting on the principal" matches what's actually open with the chief.
     - In flight matches the live sessions (session list with status), and no idle work is
       described as running.
     - Stop conditions match the handover and the live lanes. If parked, Status is a complete park
       record.
     - Move technical decisions older than a few days, and attempts beyond the last ten, to
       `lead/archive-YYYY-MM.md`, so the log stays under about 250 lines.
     - The header points to `{{BRIEF_DIR}}/chief.json` for the chief.
      - At EVERY checkpoint, park, goal completion and before handover, sweep using the
        lead core's Worktree hygiene rule and engineering practice. Remove only our
        quiesced clean merged or explicitly abandoned worker worktrees in the same step;
        keep branches. List EACH retained path, owner/state and reason in LEAD.md's Kept
        worktrees, with secondary count / 8 (all owners/branches; main excluded). At 8,
        clean before creating a ninth; above 8, sweep immediately. Never force or erase
        dirty/untracked/ignored data, touch another owner or strand an active session cwd.
        If protected/dirty/locked/unknown remain, create no more; serialize or pause.
        Non-git projects record N/A. Retention/refusal is an honest sweep outcome.
   - **Both:** full sentences with normal spacing, plain words, and nothing stale.
3. **Check.** Read the files as if you were a brand-new session that has never seen this
   conversation. Can you tell who is doing what, what's waiting on whom, what was promised, and
   what comes next? Fix anything that leaves you guessing.
4. **Report.**
   - **The chief** says one sentence, such as "Files are current: six questions open, two
     promises." Then it puts a short list of what changed in the detail block.
   - **A lead** adds one line to its turn report.

## Fresh session

Do this only after steps 1 to 3 are done.

**The chief of staff:**

1. Start a new chief session in `{{BRIEF_DIR}}` (your host section gives the exact call):
   - agent `{{CHIEF_AGENT}}`
   - title "Chief of staff"
   - your current model, unless it's out of usage
   - no goal mode
2. Use this prompt: "You are the principal's chief of staff, continuing from an earlier session.
   Read AGENTS.md, then brief.md, open.md and principal.md. Write your session id into chief.json.
   Then say in one sentence that you're ready, and how many questions are open."
3. When it has replied, check that `chief.json` holds its id.
4. Tell the principal in one sentence to pin the new "Chief of staff" session; this one can be
   archived.
5. Anything that still arrives here afterwards, forward to the new session.

**A lead:**

1. Start a new session in the project folder:
   - agent `{{LEAD_AGENT}}`
   - title "[lead] <Project>"
   - goal mode on
   - a prompt that starts with "Goal:" and the objective from your log, followed by "Continuing
     from an earlier session: read LEAD.md first."
2. Update the session id in your log's header.
3. Tell the chief the new id, so it can update the brief.
4. Send every running worker one line with the new id to send questions to.
5. Forward anything that still arrives in the old session.
