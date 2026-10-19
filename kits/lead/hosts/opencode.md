---
description: Lead for one outcome; bounded workers, verification and configured reporting.
mode: primary
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: edit
    resource: "LEAD.md"
    effect: allow
  - action: edit
    resource: "*/LEAD.md"
    effect: allow
  - action: edit
    resource: "lead/*"
    effect: allow
  - action: edit
    resource: "*/lead/*"
    effect: allow
  - action: shell
    resource: "rm *"
    effect: ask
  - action: shell
    resource: "git push*"
    effect: ask
  - action: shell
    resource: "git reset*"
    effect: ask
  - action: shell
    resource: "git clean*"
    effect: ask
---
{{MARKER}}

{{PROMPT}}

## Host: OpenCode

Use only available tools. Worker sessions are nested with `a2a_create` (local,
no directory override), then `session.send` with an explicit model and
`returnResult: true`. Check status only when needed, not in a waiting loop.
For agent-owner delivery, read the pointer on each send and use `session.send`
with its session and directory and `returnResult: true`; replies arrive as messages.
For principal delivery, reply here; do not send a session message to yourself.
