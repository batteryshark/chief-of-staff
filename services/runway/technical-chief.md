## Fleet tools

These are local shell commands. Use the ones that exist on this machine. The host section below
says which delegation mechanism comes first.

- **Routing.** `runway` (or `chief-runway`) reads Tarmac's passive snapshot, checks the target model
  catalog, reserves shared capacity and persists decisions. It is advice on usage, not a gate: the
  leads use it for their workers, and you use it for your own one-off workers and for the
  usage picture.
- **Other vendors from a plain shell (fallback).** When the host has no model route to a vendor,
  run its official CLI headless in the target directory: `codex exec "<task>"`,
  `claude -p "<task>"`, or `agy -p "<task>" --output-format json`. Do not use orchestra-next or
  dsh; they are retired.
- **Cross-machine (optional).** If `a2a_list`, `a2a_send` and `a2a_read` tools exist, use them to
  reach agents on other machines.
