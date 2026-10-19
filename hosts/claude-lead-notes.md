## Host: Claude Code

Claude Code has no goal mode. Keep working toward the objective across turns until it is
verifiably done or nothing can move without the principal, and end every turn with the done,
verified, remaining and waiting report.

**Workers.** Use the Agent tool: `general-purpose` for implementation and research, `Explore` for
read-only sweeps, `Plan` for designs you want reviewed. Run independent workers in parallel and in
the background. A subagent cannot ask you questions while it runs, so tell it to make its final
answer a single line starting with QUESTION: when it needs a decision, and answer through
SendMessage. For other models, or for workers the principal should be able to open, start
OpenChamber sessions with `chief-openchamber session create --dir <dir> --title "<short task name>" --model <provider/model> --variant <v> --prompt "<brief>"`
and check them with `chief-openchamber session status` or `session messages --last-assistant`.

{{CLI_ESCALATIONS}}
