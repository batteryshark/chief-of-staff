## Shared services: Docket

Use Docket for a promised time, waiting on a download or long job, or a recurring
check until removed. Read the configured Docket checkout's `AGENT_USAGE.md`
for the CLI/MCP interface; no OpenChamber settings change is required. Docket wakes
you: do not add a sleep/poll loop. Scheduling does not authorize external contact.
# Canonical integration ownership

Docket's own [OpenCode integration](https://github.com/batteryshark/docket/blob/main/integrations/opencode/README.md),
[sandbox runtime](https://github.com/batteryshark/docket/blob/main/integrations/opencode/sandbox-runtime.md) and
[Tool Stack event journal](https://github.com/batteryshark/docket/blob/main/integrations/toolstack/event-journal/README.md)
define its accepted runtime. Reuse them; do not replay smoke or invent another dispatcher.
