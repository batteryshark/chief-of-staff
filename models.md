# Model policy

How models get picked, for the chief, the leads and their workers. There is no vendor loyalty.
Pick the class of model the work needs, then pick within that class by who has usage left and how
soon it resets. The chief keeps this file current whenever the principal says something new about
models; leads read it before they route workers.

## Classes of work

| class | for | examples today (any vendor, whichever has usage) |
|---|---|---|
| Strong | the chief and every lead; design, architecture, hard debugging, reverse engineering, independent review, anything taste-sensitive | Claude Opus 5.5 (high), GPT 6.1 Sol (high or xhigh), Gemini 3.1 Pro (high) |
| Workhorse | implementing from a clear brief, ports, test passes, integration work | Claude Sonnet 5.5, Claude Opus 5.5 (medium), GPT 6 Astra (medium) |
| Visual and 3D | modelling, art direction, shaders, scene and look work | GPT 6 Astra (max), Claude Opus 5.5 (high) |
| Fast | lookups, inventories, log reading, mechanical edits, simple scripts | Claude Haiku 5.5, GPT 6 Luna, Gemini 3.8 Flash |
| Research | reading and summarizing current sources on the web | Fable 5.1, or any Strong model with web access |
| Open models | whenever the principal wants them, or to try one out | local models; free models; paid ones only as below |

The chief and the leads stay in the Strong class, whichever vendor that is today. Workers go in
whatever class their job needs.

## Usage

- Within a class, prefer the allowance with the most left relative to how soon it resets. Usage
  left unspent at a reset is wasted. `runway` does this arithmetic from Tarmac's numbers; read its
  status before a batch of dispatches.
- **Read usage when work starts.** Before dispatching anything new, read `runway`'s `usage`
  action (from the shell: `echo '{"action":"usage"}' | chief-runway`). It reads Tarmac right then.
- **Burn mode is automatic at dispatch.** An allowance is burnable when a weekly window has at
  least 20% left within a day of its reset, or a 5-hour window has at least half left within two
  hours of its reset. New work goes there first, and it's a good moment to fan out. Allowances at
  10% or less are listed as low; start new work elsewhere. The thresholds can be changed with a
  `burn` object in `~/.chief-of-staff/runway/routes.json`.
- **Burn on request.** The principal can also call a burn the watch didn't flag ("we have Claude to
  burn, fan out"). The chief records it with `runway`'s `prefer` action.
- **Out of usage.** Running work stays where it is. If it runs out and stops, continue it from its
  checkpoint on another model in the same class. New work goes elsewhere right away.
- These calls are made by the chief for itself and the leads, and by each lead for its
  workers. Nobody waits for the principal to pick a model unless they want to.

## Paid, pay-as-you-go models

DeepSeek, OpenRouter, and anything else billed per use from credits are never chosen by default,
never used to stretch a subscription, and never burned.

- They are used only in a project where the principal has given explicit permission for that
  project. The permission is recorded under Principal decisions in that project's `LEAD.md`
  and in the chief's brief, with which models and any limit the principal set.
- The principal can withdraw it at any time. When that happens, the chief tells the lead at
  once. The lead starts nothing new on paid models, stops its paid workers at their next
  checkpoint (or right away if the principal says so), and continues them on subscription models.
- A worker that ran on a paid model under an earlier permission doesn't keep it. Continue it on a
  subscription model unless the project's current permission covers it.
- The usage table shows paid credit balances so everyone can see them, marked PAID.

## Trying things

Running a model on real work just to see what happens is allowed and encouraged, for example
Astra on a 3D asset, or a fast model on a whole worker lane. Mark the worker's title with
`(trial)`, keep a Strong reviewer on anything it produces that matters, and add a one-line verdict
under Findings.

## Principal's notes

- (Record your own model preferences and permissions here.)

## Findings

- (date: model, task, what happened, and whether to use it again)
