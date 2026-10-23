# Docket boundary

Docket owns scheduling/event implementation, lifecycle and portability. The kit reuses
its existing identity-bound, locked own-row milestone writer; it does not enroll/release
leads or replace Docket with another dispatcher. Held/archived/unknown recipients refuse
kit-owned continuation; raw host/UI and goal-loop paths have separate stated limitations.

Canonical Docket documentation:
- [OpenCode integration](https://github.com/batteryshark/docket/blob/main/integrations/opencode/README.md)
- [Sandbox runtime](https://github.com/batteryshark/docket/blob/main/integrations/opencode/sandbox-runtime.md)
- [Tool Stack event journal](https://github.com/batteryshark/docket/blob/main/integrations/toolstack/event-journal/README.md)

Coordinate role/shared-registration migration with Docket's owner at a clean checkpoint.
Do not restart its service, replay accepted smoke, or change its session/model/goal/row.

## Own-row milestone contract

`milestone.mjs` registers `docket_milestone` only with an explicit trusted binding.
Input contains only `milestone_at` and `milestone_ref`. The executor checks the
configured native session/agent, Location, archive state and `docket_milestone:own`
permission. The fixed Python executable runs `-E -s -B -m docket.milestone` in the
fixed source root; no model-supplied environment, owner, path or session selector
is accepted. The installer pins hashes of milestone.py, checkins.py, parse.py and
__init__.py from its selected Docket source. Other imports, interpreter and host
remain trusted dependencies; hashes do not isolate same-UID writers or atomically
pin bytes through execution.

The owner helper requires an existing matching session/Location row, preserves
state, unknown fields, other rows and private0700/0600 metadata, and refuses
observed conflicts without repairing privacy or enrollment. Cooperating flock
plus final byte/identity checks is **not CAS against arbitrary writers**. Native
identity checking is not atomic with a later session move. Only exact success
receipts are returned; nonzero, malformed, killed or ambiguous outcomes are
`unknown`: inspect through the owner, never retry automatically. Installation and
readback publish no live milestone and do not establish future real-use acceptance.

## Specialist launch limitation

Declared specialists must use their tool-owned launcher. `access/model.json` and
`launch_acceptance` compare launcher, session, agent, provider/model/variant,
Location, session-policy and binding digest. Matching supplied fields still return
`not-ready` without an actual launcher receipt verifier. This candidate interface
is not native prevention or production provenance proof; Galley's launcher is
not duplicated.
