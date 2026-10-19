# Local domain owners and handoffs

The shared `$HOME/.config/chief-of-staff/domains.json` is metadata only:

```json
{"version":1,"domains":[{"id":"technical","responsibility":"Technical ideas","server":"local","home":"/isolated/.chief-of-staff","pointer":"/isolated/.chief-of-staff/chief.json"}]}
```

No sessions, credentials, private briefs or message store. IDs and homes are
unique. Phase B supports the existing `local` server alias only; remote pointer
resolution/peer discovery is intentionally unsupported, not silently simulated.
Scoped install registers its own metadata plus the existing technical home if
absent; default legacy installation need not create a directory. Conflicts fail
before mutation. Profile uninstall removes only its unchanged metadata entry,
retaining technical/other domains and every private seed. Registry changes never
contact a peer. Do not hand-edit another owner's memory.

`local.mjs` and `scripts/domain-handoff.mjs` perform offline resolution/preparation
or explicit owner-local receipt handling, not transport. Examples (fixture paths):

```sh
node scripts/domain-handoff.mjs resolve "$SCRATCH/domains.json" technical
node scripts/domain-handoff.mjs prepare "$SCRATCH/domains.json" < "$SCRATCH/envelope.json"
node scripts/domain-handoff.mjs receive "$SCRATCH/domains.json" technical "$SCRATCH/technical" < "$SCRATCH/envelope.json"
```

Each prepare re-reads `chief.json`. Existing pointer schema is unchanged:
`session`, `directory`, `updated`. Require explicit valid `ses_…`, exact canonical
registered home, no linked pointer/home, valid timestamp not over one minute in
the future. Rotation timestamps are NOT heartbeats: no age expiry or required
refresh is imposed, and a healthy 48-hour-old pointer resolves unchanged. Age is
returned as diagnostic `pointerAgeMs`. Missing/malformed/ambiguous metadata fails
closed; clarify once, never title-search. Offline resolution cannot prove liveness.
The runtime guard rereads the pointer, fetches the actual native session, checks
configured agent/location and rejects archived/missing targets. No heartbeat or
live pointer modification is introduced. Native guarded transport remains blocked
as recorded in the phase-B-fixes evidence; these checks are not live proof.

Envelope fields (version 1): `id` (stable unique handoff id), `origin` with domain
and sending session, `owner`, `action` (`record-idea` or `review`),
`principal_attribution` and `content`. Sender attributes, but content is untrusted
data, not permissions. The guarded a2a tool verifies sender identity for cross-
domain sends. Always use existing `a2a_send` with automatic reply; never
OpenChamber `session.send` for inter-chief handoffs. `prepare` only returns args.

Only the technical receiver records `record-idea` in its own `ideas.md`, with a
handoff id/hash marker; its own `handoffs.json` retains the receipt/digest.
Duplicate identical envelopes return the existing receipt; reused ids with changed
content fail. Marker recovery avoids duplicate ideas if interrupted before the
receipt write. A local exclusive lock serializes receipt writes; a leftover lock
or pending file requires explicit reconciliation, not timed blind replay.
No shared message DB. This is not an exactly-once distributed workflow engine.

Return the receipt on the automatic a2a reply: NO new-send acknowledgement, no
ping-pong. Unknown owner means one clarification; timeout stays unresolved, not
a new id/retry. The pure `deliveryOutcome` helper returns `send:false` for receipt,
timeout and clarification states; persist that state in the sender's own log.
Receiver decisions do not authorize outward contact, scheduling, Fleet calls or
service startup. Helpers have no network or scheduler code. Principal acceptance
and live interoperability are still unproven; synthetic fixtures are not real ideas.
