# Optional heartbeat runtime

File-backed, origin-bound coordination for an explicitly configured chief and lead
set. This directory contains runtime source and deterministic offline tests, not
private pilot history, enrollment manifests or evidence of a live installation.
The ordinary chief inbox/direct-owner fallback remains available; rendering roles
does not activate this integration. See [integration contract](INTEGRATION.md) and
[installer boundaries](KIT.md) before configuring it.

## Boundaries

- The current trusted chief pointer gates chief context/status/close/reconcile.
  Origins and goal-wait sessions are separately enrolled. Never infer authority
  from an agent name, stale pointer, report text or a card label.
- Held, archived, moved and unknown recipients refuse kit-owned continuation.
  Native app archive state, current roster identity and scoped hold records must
  all agree. A hold for one lane does not clear or stop unrelated authorized work.
- `post` records original event/ref/origin/limits; a receipt is not owner completion.
  Same-key changed payload, wrong origin and ambiguous correlation refuse. Saved
  answers are data, not permission to resume goals or perform external effects.
- Only an owned wait with matching original objective/hold bindings may resume.
  Manual stop wins. Final rereads are not atomic compare-and-swap with host/UI
  changes; raw host goal loops are outside this runtime's enforcement boundary.
- Dispatcher batches are bounded and short lived. Standing decisions may cover an
  answer; new judgment goes to the current chief. There is no second portfolio
  ledger, general scheduler, automatic principal-card approval or phone service.
- Unknown admission/effect outcomes stay uncertain. Durable intent, origin binding
  and no-replay fences are not an exactly-once delivery guarantee. Record-only
  closure must not be mistaken for delivery or an authorized external effect.

The complete tool schemas are in plugin.mjs. Watched entries are disabled until
explicit options are installed. Maintenance is limited to existing owned runtime
and watched entries and preserves options, recipient topology, goals and holds.
No supplied public profile enrolls a session, and no scanner or test replaces the
operator's final installed-role compatibility acceptance.

## Offline checks

From the repository root, with Node and Python prerequisites available:

```sh
node --test heartbeat/*.test.mjs
PYTHONPATH=scripts:tests python3 -B -m unittest test_heartbeat_install
```

These use synthetic records/transport doubles and temporary filesystem state.
They do not send a phone card/call, launch model workers, install a live service,
change a lead identity or prove live end-to-end delivery. Runtime state, rosters,
credentials, receipts and operational logs belong outside this repository.
