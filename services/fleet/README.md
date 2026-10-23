# Fleet registration rule

Canonical short instructions are `kits/shared/fleet.md`, composed into BOTH
chief and lead prompts. Source verified read-only:
the configured Fleet checkout's `README.md` (commands and config sections).
Registry: `~/.config/fleet/services.json`.

On macOS, for every background service a lead installs within approved authority, register it in the
SAME step using documented `fleet add` / `fleet adopt`, with `--port`, `--probe`
and `--group`. Follow Fleet's documentation for the required add execution or
adopt label arguments; this module does not invent another interface. The
principal can then list/start/stop centrally. Registration is necessary, not
permission to install/start a background service. The approved initial project plan may already
authorize it; do not ask again when covered. Existing constraints and tool permissions remain.

Check the operator's existing registry before adopting a service; avoid duplicate
adoption. This grants no permission to probe, start or install services. Even
listing Fleet may initialize its config; offline fixtures must not invoke it.
