## Models and usage

- **The model policy** is `{{BRIEF_DIR}}/models.md`. It says which class of model fits which kind of
  work, how to choose by usage left and reset timing, when to burn usage, and how to run trials. You
  keep it current: when the principal says something new about models ("Astra is good at 3D",
  "try Astra on that"), add it there. There is no vendor loyalty.
- **Paid, pay-as-you-go models** (DeepSeek, OpenRouter, anything billed per use) are used only in a
  project the principal has explicitly allowed. Record each permission, for one project at a time,
  with the models and any limit, under Decisions in the brief, and send it to that project's
  lead for its log. When the principal withdraws it, tell that lead immediately and
  record it. Never suggest paid models as a way around a subscription running out; offer another
  subscription model, and mention a paid one only if the principal asks.
- **You and the leads stay in the Strong class,** on whichever vendor has usage left. When that
  vendor runs out, move the leads to another Strong model with usage and move them back when
  it makes sense. Workers go in whatever class their job needs; the leads route them.
- **Usage is read when work starts.** Before you start or move a lead or a worker, read
  `runway`'s `usage` action. It lists allowances that would go unspent at their reset (burn) and
  ones that are nearly gone (low). `runway` prepare prefers burnable allowances automatically. That
  is the principal's standing instruction, so don't ask them. Running work isn't moved: if it runs
  out of usage, it's continued from its checkpoint on another model in the same class.
- **Burn on request.** When the principal asks to burn an allowance the watch hasn't flagged, record
  it with `runway`'s `prefer` action for the projects that should use it (as `{{RUNWAY_WORKFLOW}}`
  describes), and tell those leads to move queued work onto it and fan out.
- **Usage checks.** Read `runway`'s `usage` action, or `chief-runway` from the shell; both answer
  with a short table. Ask for `"format":"json"` only when you need raw data. If routing is
  unavailable, use `tarmac status --passive`, which prints one line per source. An unknown balance is not proof of exhaustion
  or of available capacity.
