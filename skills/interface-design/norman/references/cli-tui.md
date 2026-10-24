# CLI & TUI — the same principles at the prompt

Full-parity reference. A blank prompt has zero signifiers; everything the user
can discover arrives through a small, auditable inventory. Anchor source:
clig.dev (Command Line Interface Guidelines); lineage: POSIX utility
conventions → GNU standards (`--help`/`--version`, uniform long options) →
Heroku's 12 Factor CLI Apps → clig.dev.

## Norman at the prompt — where the mapping is real

- **Signifiers:** the usage line, `-h`/`--help`, man pages, no-args help,
  "did you mean" suggestions, shell completion. Completion is an interactive
  signifier — it exposes the option space at the moment of need, converting
  recall to recognition. A missing one of these is the CLI's unmarked door.
- **Feedback:** "silence is success" is a documented failure for interactive
  use. Print something within ~100ms; report what changed after state
  changes; progress for long operations; exit codes for machines, printed
  words for humans; stdout for data, stderr for messages.
- **Constraints & forcing functions:** confirmation prompts, `--force` as the
  explicit interlock override, `--dry-run` as the zero-cost rehearsal, typed
  resource-name confirmation for the severest actions. Textbook DOET.
- **Conceptual models:** git is the canonical misfit study (Perez De Rosso &
  Jackson, Onward! 2013 / OOPSLA 2016): clean data model, command surface
  misaligned with it — `checkout` did three unrelated jobs until git itself
  conceded with `switch`/`restore` (2019). When commands span concepts, users
  suffer regardless of how clean the internals are.
- **Strained:** "affordance" barely applies — a terminal affords typing
  anything. Almost everything at the prompt is signifier work.

## Interaction cost at the prompt

The CLI ledger: keystrokes, flag memorization (pure knowledge-in-the-head),
help/man/StackOverflow lookups (an undocumented flag converts a 1-second
recall into a multi-minute search), completion (the single biggest cost
reducer), defaults (the zero-flag invocation should do the common thing).

**The cost asymmetry is the design decision:** CLIs amortize — high first-use
cost, near-zero hundredth-use cost. Right for daily developer tools; wrong for
occasional-use tools (installers, migrations, certbot-alikes), which should
prompt or wizard when interactive. clig's rule reconciles both: prompt when
stdin is a TTY, never *require* the prompt (`--no-input` escape hatch).

## Error messages — the Elm/Rust standard

One block answering: what happened, where exactly, what to do next. Rewrite
expected errors for humans, with the fix in the message ("Can't write to
file.txt. Try: chmod +w file.txt"). Most important line last (where the eye
lands). Unexpected errors → bug-report URL. No raw stack traces for expected
failures. (Czaplicki, "Compiler Errors for Humans," 2015; Rust, "Shape of
Errors to Come," 2016 — both treat errors as a designed UI surface.)

## TUI patterns

- **Persistent key footer** (htop's F-keys, nano's `^X Exit`, lazygit's hint
  bar + `?` cheatsheet): the door handle of the TUI. Ship one.
- **which-key pattern** (after a prefix keypress, show all continuations):
  recall → recognition mid-chord; now built into Emacs 30 and neovim distros.
- **Visible mode**: unmarked modes violate visibility of state — vim's
  `-- INSERT --` is the minimal concession; do better.
- **Miller columns** (ranger, Finder): hierarchy context + current position
  always visible — "where am I" answered structurally.
- Bubble Tea's Elm architecture (model/update/view) is conceptual-model
  discipline for TUIs; state lives in one place, the view renders it.

## Flag bloat

curl carries 265+ options and stays usable because the common cases stay easy
and the docs curate a common path (Stenberg's stated rationale: protocol
count × independent toggles × never-remove compatibility). The lesson is not
"many flags fine" — it is that surface area demands curation: umbrella flags,
help categories, examples-first docs. Gunnerson's minus-100 applies to flags
doubly: flags are forever and compose combinatorially. clig's guards: no
near-synonym subcommands (update/upgrade), no catch-all default subcommand, no
auto-accepted prefix abbreviations (they foreclose the namespace).

## The 12 mechanical checks (auditable from source alone)

1. `-h` and `--help` work on every subcommand, exit 0; `-h` never overloaded.
2. `--version` exists.
3. No-args run of an argument-requiring command prints concise usage + one
   example — not a hang, not a traceback.
4. Help contains at least one worked example per command; usage line follows
   POSIX/docopt grammar; `--` supported.
5. Every flag the parser accepts appears in help text (diff parser vs docs —
   undocumented flags are orphaned capabilities); every short flag has a long
   form.
6. Data → stdout; messages/progress/logs → stderr; exit 0 on success, nonzero
   and differentiated on failure.
7. Color/animation off when not a TTY, when `NO_COLOR` is set, or
   `--no-color`; prompts skipped when stdin is not a TTY; `--no-input`
   exists and missing input then fails naming the flag to pass.
8. Destructive operations: confirmation or explicit `-f/--force` or
   `--confirm=<name>`, plus `-n/--dry-run`.
9. Standard flag vocabulary (`-q`, `-v`, `-o`, `--json`/`--plain`, `-n`);
   no near-synonym subcommand pairs; no catch-all default subcommand; no
   prefix abbreviations.
10. Unknown input → "did you mean" (never auto-executed) or at minimum names
    the bad token and points at help.
11. Errors state cause and a concrete next action; no bare stack traces on
    expected failures.
12. TUIs: current mode always visible; available keys surfaced on screen
    (footer, `?` cheatsheet, or which-key popup).

## Folklore corrections

- "Git is a beautiful functional data structure with a terrible CLI" — the
  first half is Nilsson (2013); the second half is internet accretion. The
  citable critique is Perez De Rosso & Jackson's concept-misfit analysis.
- The vim "learning cliff" curve is a meme, not data; the sourced critique is
  unmarked modes vs visibility of state.
- "GNU tools are bloated" is aesthetics (Pike's cat -v talk), not measurement;
  the measurable claims are option-count growth and help-text length.
