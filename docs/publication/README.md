# Public source boundary

This is a minimal hygiene update on existing public history, not the pending
private-source runtime repair release. It removes retired native desk code/tests
and corrects setup guidance. Other existing public content is retained. Historical
filing guides/installers are not supported activation routes.

Preserve LICENSE, RIGHTS, ATTRIBUTION, artwork and THIRD_PARTY_NOTICES unchanged.
The source declares locked dependencies, not vendored packages; retain supplied
licenses/notices when redistributing installed packages or built bundles.

Never merge or push the private development repository/history. Future exports
must select reviewed tracked source, excluding lead reports, PROJECT/LEAD logs,
evidence, archives, runtime enrollment profiles, personal model policy, state,
credentials, .env files, installed dependencies and private Git objects. If an
installer expects a reference/config file, supply generic templates, never a real
machine/session enrollment. Existing public templates remain templates, not proof
of live setup or dispatch compatibility.

Before publication, review both the diff and all reachable public history. Run
existing bounded tests and a real isolated-HOME install/export/uninstall check.
Run Gitleaks with default rules on the full proposed payload and history:

```sh
gitleaks dir --redact --ignore-gitleaks-allow --no-banner .
gitleaks git --redact --ignore-gitleaks-allow --no-banner --log-opts=--all .
```

A clean secret scan is not a privacy review: separately inspect hardcoded user
paths, real session IDs, private IPs, tailnet hosts and live enrollment records.
Re-scan after any change. Do not publish scan reports or local evidence. The
lead owns integrated repaired-source selection and final native compatibility
acceptance. Publishing still requires explicit approval and a non-force push of
only the reviewed public commit; no private branch, all-refs, tags or mirror push.
