# Docket

Canonical short guidance is `kits/shared/docket.md`, included in chief and lead
instructions. Read the configured Docket checkout's `AGENT_USAGE.md` for CLI/MCP details.
Do not copy its API, create another service or edit OpenChamber settings. Docket
wakes agents for promised times, download/long-job waits and recurring checks
until removed; no sleep/poll loops. No handoff creates a schedule automatically.

Check the operator's existing Fleet registry before adopting Docket; avoid
duplicate adoption. This grants no permission to probe, start or install it.
