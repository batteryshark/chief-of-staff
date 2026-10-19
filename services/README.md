# Shared services: references, not duplicate instances

The kit owns composition and narrow host adapters, not these services' lifecycles.
No installer in this kit starts a daemon, registers a schedule, contacts a phone,
or grants permission to do so. Registration/configuration is not execution proof.

- [Models](models/README.md): one installed policy, maintained by the technical owner.
- [Runway/Tarmac](runway/README.md): one registry/ledger per account-owning host.
- [Docket](docket/README.md): existing promised-time and wakeup service.
- [Voicestack](voicestack/README.md): current technical chief only; request via owner.
- [Fleet](fleet/README.md): every approved new background service registered in the
  same installation step; existing adoption is not repeated.
- [Local directory](directory/README.md): metadata and offline handoff helpers,
  existing a2a transport, private owner-written receipts.

Independent leads do not require a chief's memory or services. Their supplied
model/routing policy remains optional; the principal's short Docket/Fleet rules
are still included. An unavailable tool is a limitation, never authorization to
expose a broader one. Scoped profiles refer to the installed shared policy and
ledger and never seed alternate copies. The narrow example requests operations
it cannot perform from the appropriate owner rather than bypassing its catalog.
