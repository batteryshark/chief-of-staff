# Native dispatch installation

The existing routing installation remains dispatch-disabled when `hostDispatch`
is absent. Installation never supplies credentials, enrolls a lead, changes a
session/model/goal, launches a worker or creates a second admission ledger.

For an explicitly authorized Location, prepare an owner-reviewed JSON manifest:

```json
{
  "location": "/absolute/current/project",
  "hostDispatch": {
    "chiefPointerFile": "/absolute/current/project/chief.json",
    "holdBindings": {
      "/absolute/current/project": [
        {"file": "/absolute/current/project/LEAD.md", "heading": "## Stop conditions", "allowedQuote": "Exact currently approved section; never manufacture an all-clear."}
      ]
    },
    "workerAgent": "build",
    "completionTimeoutMs": 25000
  }
}
```

Use the genuine current chief pointer and/or active enrolled lead `rosterFile`,
as applicable, and current project holds. A lane uses `lane` plus the existing
`{global: [...], lanes: {name: [...]}}` hold form. `workerAgent` is required at
execution when the reserved route has no agent. Archive checks inherit the
existing authenticated OpenChamber agent-tool connection. Missing or unknown
identity, archive or hold state fails closed; there is no fixtureMode.

```sh
node scripts/build.mjs
python3 -B scripts/install-routing.py "$PWD" dry --dispatch-config /approved/manifest.json
python3 -B scripts/install-routing.py "$PWD" install --dispatch-config /approved/manifest.json
```

For a disposable installed check only, `node scripts/build.mjs /fixture/runtime`
builds into an isolated output instead of touching the globally loaded dist.
The manifest's optional absolute `pluginRoot` must stay inside its `location`.
The scoped installer writes only that Location's `.opencode/opencode.json`,
preserving unrelated options; it never rewrites global configuration, launchers
or routes. A scoped build adds only two exact Location-local integration-deny
rules for the old global dist path/entry, preventing a duplicate plugin ID.
Never copy a fixture pointer/hold binding into production rollout.

The source controller remains limited to fresh same-native-Location ungoaled
workers. `prepare` must return `runway.dispatch`; actual installed acceptance
requires exact agent/selectable model ID/variant/no-goal readback and matching
native origin, input, assistant and idle IDs, plus genuine hold/archive refusal.
Raw host/UI and goal-loop paths, atomic hold/admission and crash exactly-once
delivery are not repaired or claimed. Unknown acknowledgement is not permission
to resend. See the installed `WORKFLOW.md` for explicit collection/reconciliation.
