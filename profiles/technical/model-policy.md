## Models and usage

- The model policy is `{{BRIEF_DIR}}/models.md`. Before you start new work, pick the class of model
  the job needs, then read `runway`'s `usage` action. Prefer an allowance it lists as burnable (it
  would go unspent at its reset), avoid one it lists as low, and otherwise take the model in that
  class with the most usage left relative to its reset. `runway` prepare does this automatically.
  There is no vendor loyalty.
- Paid, pay-as-you-go models (DeepSeek, OpenRouter, anything billed per use) are off limits unless
  your Principal decisions record the principal's permission for this project. Stay within the
  models and limit it names. When the principal or the chief withdraws it, start nothing new on paid
  models, stop paid workers at their next checkpoint (or at once if told to), and continue them on
  subscription models. A worker that ran on a paid model before doesn't keep it: when you continue
  it, give it a subscription model unless the current permission covers it.
- You stay in the Strong class. If your model runs out of usage, tell the chief so it can move you.
  Never move yourself to a fast or cheap tier.
- Running workers stay where they are. If one runs out of usage and stops, continue it from its
  checkpoint on another model in the same class that has usage.
- Trials are welcome: run a model on real work to see how it does, mark the worker title
  `(trial)`, keep a Strong reviewer on anything that matters, and send the chief a one-line verdict
  for the Findings section of the policy.
