# Runway and Tarmac

Actual implementation stays in `runway/`, `routing/`, `dist/` and the existing
launchers. `technical-chief.md` holds unchanged technical prompt text. The shared
registry/ledger home is `CHIEF_RUNWAY_HOME` or `<shared chief home>/runway`; scoped
chiefs never create a new registry, ledger, allowance, account or daemon. Tarmac
is external and supplies the existing passive snapshot contract.

The narrow scoped adapter does not expose unchecked Runway or shell tools. It
references the same authority and requests routing help from its technical owner;
actual catalog/permission integration is for the later bounded runtime lane.
Do not run even a status command during offline installer fixtures: ledger
construction can mutate state and observation can contact the external service.
