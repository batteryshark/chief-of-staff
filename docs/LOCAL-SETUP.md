# Local setup (no installed account defaults)

Fresh installs seed an empty Runway route list. Configure
`~/.chief-of-staff/runway/routes.json` using selectable IDs discovered in your
host, your own provider/account/pool and usage windows. The route object's
`id`, `host`, `model`, `source`, `provider`, `account`, `pool`, `windows`,
`categories`, `max_parallel` and `reserve_percent` describe that local allowance.
For instance, use `windows: "all"`, `categories: ["implement"]`,
`max_parallel: 1`, `reserve_percent: 5`; obtain model/account values from your
installed host rather than copying a fictional ID. Named models elsewhere are
technical support examples, never a promise of selectable availability.

## Optional promotional API

No promotion, zero baseline, subscription, route or renewal date is assumed.
Before the existing explicit promo installer, place these reviewed local files
in the chosen Runway directory (outside the repository), mode 0600:

- `promo-policy.json`: actual `grant_micro_usd` (positive integer micro-USD)
  and `renewal_day` (1–28, UTC accounting convention). The generic
  `routing/promo-policy.example.json` is an example only, NOT an asserted grant.
  The stop is always floor(90% of grant).
- `promo-opencode.json`: explicit provider/agent additions. Review
  `routing/api-promo.opencode.json` as a named technical example and confirm
  model IDs/rate support before choosing it; no snippet is silently selected.
- `promo-routes.json`: explicit selected `api_routes`. The named route example
  `routing/api-promo.routes.json` describes the currently supported API choices.

Then use the documented promo installer with explicit current-cycle approval,
known baseline and **mandatory Console backstop** preventing loaded-credit spend.
Manual API use is not protected by the local counter. Unknown cycles cannot
admit; unresolved reservations, receipt history, output plus reasoning accounting
and cycle authority remain durable. Renewal requires explicit verification.
Missing/invalid policy fails closed before opening the database; an existing
installation is NOT automatically migrated. Changing policy invalidates stored
dispatch authority. Parent review must reconcile existing policy/authority and
liabilities before deploying this public-only seam; no database is rewritten here.

## Nod

Copy `docs/nod-options.example.json` to a private 0600 file, set your URL and
optional approved HTTPS image base, and run `chief-nod configure FILE
--expect-absent`. Fresh installations may explicitly use `retired_sessions: []`.
Use `configure --help` for reviewed updates; protected retired IDs cannot be
removed. Ordinary isolated calls load persisted options without shell exports.

## Portability inventory

Newly local: promotion grant/renewal/derived stop, selected subscription route
roster/accounts/windows, explicit optional API model/provider additions, and Nod
routing/image/retired-session options. The old selected route roster is not
installed; practical named provider support examples and synthetic tests remain.
Already public-sanitized/local: household hosts/IPs, personal project/home paths,
real Nod endpoints, chief identities and ledgers. None were newly discovered or
migrated from a live installation. Generic Runway/Docket/Tower hooks, prompts,
licenses and public ancestry remain. Both complete MIT Norman packages are
vendored; installation does not need a private `_skills` tree.
