{{MARKER}}
# Home infrastructure — operator setup template

This is a generic template, not a machine inventory or live enrollment. Configure
optional services separately; basic role rendering does not require them. Keep real
addresses, session pointers, rosters, credentials and operational records outside
this repository. No service or model is started by installing these instructions.

- Nod: set NOD_BASE_URL (or CHIEF_NOD_URL for chief decisions) to your configured
  server. The portable default is loopback port 8767, not a discovered service.
  Supply issuer credentials through NOD_ISSUER_TOKEN_FILE or CHIEF_NOD_TOKEN_FILE;
  never commit a token. Use `nod-alert --dry-run` or `chief-nod ask --dry-run` first.
- Images: set CHIEF_NOD_IMAGE_BASE to a separately authorized HTTPS image route before
  sharing an image. The example.invalid default is deliberately nonfunctional.
  Only explicitly selected images should be made readable. The kit does not
  configure Tailscale, Fleet, a public listener or a background image service.
- Chief identity: keep the current trusted chief.json in your private brief folder.
  A template pointer is not a session enrollment. Do not invent session identities.
- Fleet/Docket/Tarmac: follow the separately configured dependency's documentation.
  Register an authorized background service only when the operator's plan covers it.
  No live registry/roster, goal, hold or principal preference is supplied here.
- Shared skills: `~/_skills` is the portable home root. `/example/shared-skills`
  in exported policy fixtures is an illustrative external root, not an existing
  machine binding; review permissions for your environment before installation.

See docs/chief-nod-continuation.md and heartbeat/INTEGRATION.md in the source kit
for optional origin-bound delivery contracts and their limitations.
