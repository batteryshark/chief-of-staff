# Pi setup and interfaces

Use `@earendil-works/pi-coding-agent@1.0.0`, Node.js 22.19.0+ and Pi's default
`~/.pi/agent` directory. Configure the host, model and permissions separately.
The kit doesn't inspect your installation, settings, credentials or running sessions.

The [README setup](../README.md#pi-10) installs two prompt templates,
`prompts/chief-of-staff.md` and `prompts/chief-lead.md`, plus skills
`chief-shape`, `chief-checkpoint`, `chief-lead-checkpoint` and `upstream-courtesy`.
It also copies the seven read-only service guides under
`~/.pi/agent/chief-resources/services`. Those guides are references to separately
configured services; their presence supplies no tools or automatic wakeups.
Chief seeds `brief.md`, `open.md` and `principal.md` once in its selected brief
folder. Existing seeds are never overwritten or deleted.

Start Pi in the brief folder and invoke `/chief-of-staff <request>`. Start a
project conversation in the project folder and invoke `/chief-lead <objective>`.
Pi expands a template's `$ARGUMENTS` into the current conversation. Skills load
through `/skill:<name>`; a fresh conversation must load its role template again.
Run `/reload` in an open session after updates. Review resource trust and slash
command collisions before use. The kit neither rewrites Pi settings nor registers
executable extensions or named child agents. Custom agent directories and disabled
resource discovery need operator setup outside this preset.

## Optional packages under Pi

Review and install these external prerequisites separately if wanted. Upstream's
package-manager commands are:

```sh
pi install npm:pi-subagents@0.79.1
pi install npm:pi-goal-x@0.32.3
```

These commands install third-party code that executes when Pi loads it. Chief's
installer never runs them. Select either or both guidance flags, preview, then
reinstall with the same flags:

```sh
./install.sh --profile pi --pi-capability pi-subagents --pi-capability pi-goal-x --print
./install.sh --profile pi --pi-capability pi-subagents --pi-capability pi-goal-x --dry-run
./install.sh --profile pi --pi-capability pi-subagents --pi-capability pi-goal-x
```

Omit either flag to select only one. Installation without flags removes optional
guidance from the prompts; it doesn't unload packages configured by the operator.
`./install.sh --profile pi --uninstall` needs neither extension and leaves their
settings, packages and goal data alone. Missing tools block that integration
action; ordinary permitted work can continue.

### pi-subagents 0.79.1

The package is [nicobailon/pi-subagents](https://github.com/nicobailon/pi-subagents/tree/95683a4427e1e4af8de03f1a9ca03ec4c2799b73).
Its source manifest loads `index.ts`, skills and prompts; the published npm
manifest loads `index.js`. The ai peer range `>=0.86.1` admits 1.0.0; coding-agent,
agent-core, tui and typebox peers use `*`. The kit bundles none of its code.

The [activation implementation](https://github.com/nicobailon/pi-subagents/blob/95683a4427e1e4af8de03f1a9ca03ec4c2799b73/src/extension/tool-activation.ts)
exposes `subagents_enable({})` when lazy activation is enabled. It makes the full
`subagent` tool available on the next model request and launches nothing.
The [schema](https://github.com/nicobailon/pi-subagents/blob/95683a4427e1e4af8de03f1a9ca03ec4c2799b73/src/extension/schemas.ts)
and [tool reference](https://github.com/nicobailon/pi-subagents/blob/95683a4427e1e4af8de03f1a9ca03ec4c2799b73/docs/tool-reference.md)
define top-level `agent`, `task`, `async`, `cwd`, `action`, `id`, `message` and
nested `options` for timeout/context/share/guide topic. Discover the actual agents;
prompt templates do not register child agents. Chief can pass the full included
lead prompt as a bounded worker's task, with its project cwd and constraints.
Child questions/blocks must return through the package's supported result or
supervisor facilities; no OpenChamber `session.send` contract is supplied.

Foreground children lack ambient extensions, including goal tracking. They can
return a bounded delivery slice for Chief to review, checkpoint and continue with
an eligible retained-child resume. Async launch receipts need later settlement
checks using the exact returned id. Resume creates a new child from retained
context and may refuse; stopped runs aren't resumable. Independent main Pi lead
conversations report to the principal locally, who carries reports to Chief.
There is no durable remote Chief session target or automatic successor handoff.
Web research needs separately configured child web tools. Finite fanout, deadlines,
one writer per file set and separate cumulative-spawn limits remain necessary.

### pi-goal-x 0.32.3

The package is [tmonk/pi-goal-x](https://github.com/tmonk/pi-goal-x/tree/64c5ace87f3400c0b55ef87f2d2912167f53dbaa).
Its manifest loads `extensions/goal.ts`. Host peers `>=0.83.0 <2.0.0` admit Pi
1.0.0; typebox requires `^1.3.11`. Its Node minimum is 22.15.0, so Pi's higher
22.19.0 minimum applies. It has no pi-subagents prerequisite and owns its optional
completion auditor.

Only the included lead receives this guidance; Chief never starts its own goal.
The [core tools](https://github.com/tmonk/pi-goal-x/blob/64c5ace87f3400c0b55ef87f2d2912167f53dbaa/extensions/goal-core-tools.ts)
are `get_goal`, `create_goal` and `update_goal`. Selection doesn't activate a goal.
Creation requires explicit operator authorization; verify focused goal identity,
objective and execution ownership before binding work. Operator commands `/goal`,
`/sisyphus`, `/goal-focus`, `/goal-pause` and `/goal-resume` control planning, focus
and execution. Another session needs explicit resume to take execution ownership.

Active goals auto-continue. Unset `maxAutonomousRuns` is unlimited; zero disables
continuation. Have the operator choose an allowance in `/goal-settings`; resume
renews its period. The allowance doesn't bound within-run tool loops or turns
started by unrelated extensions. Strict ready/wait declarations require the
operator's `strictExecutionContract` opt-in; retain returned wait identity and
deadline. Timers need Pi open. See [advanced semantics](https://github.com/tmonk/pi-goal-x/blob/64c5ace87f3400c0b55ef87f2d2912167f53dbaa/docs/advanced-usage.md).

Pause an owned active goal immediately on a stop, decision or handover with
`update_goal({status: "paused", reason: "<stop reason>"})` and verify success. `blocked` has
a separate same-blocker/three-consecutive-turn policy. Completion requires actual
verification and checking the returned completion state; an enabled auditor can
reject the completion request. Default goal data is `.pi/goals` in the selected
pool; focus is session-local. Package child completion and goal continuation are
separate contracts. No OpenChamber goal binding or external wakeup is added.

## Source and verification boundary

Pi interfaces were checked against [v1.0.0, commit a13d35a](https://github.com/earendil-works/pi/tree/a13d35a742c6ef8462812a28fbe1d8c8b7431c32/packages/coding-agent),
including its [prompt templates](https://github.com/earendil-works/pi/blob/a13d35a742c6ef8462812a28fbe1d8c8b7431c32/packages/coding-agent/docs/prompt-templates.md)
and [skills](https://github.com/earendil-works/pi/blob/a13d35a742c6ef8462812a28fbe1d8c8b7431c32/packages/coding-agent/docs/skills.md).
The extension pins above correspond to v0.79.1 and v0.32.3. Static peer ranges
admit Pi 1.0.0. Offline fixtures verify kit composition, real discovery paths,
optional guidance isolation and owned file lifecycles. Live Pi loading, extension
execution, model calls, worker delivery and goal continuation remain untested.
