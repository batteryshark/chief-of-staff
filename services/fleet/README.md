# Fleet registration rule

Canonical short instructions are `kits/shared/fleet.md`, composed into BOTH
chief and lead prompts. Source verified read-only:
the configured Fleet checkout's `README.md` (commands and config sections).
Registry: `~/.config/fleet/services.json`.

For every background service a lead installs with approval, register it in the
SAME step using documented `fleet add` / `fleet adopt`, with `--port`, `--probe`
and `--group`. Follow Fleet's documentation for the required add execution or
adopt label arguments; this module does not invent another interface. The
principal can then list/start/stop centrally. Registration is necessary, not
permission to install/start a background service. Existing approval gates remain.

Check the operator's existing registry before adopting a service; avoid duplicate
adoption. This grants no permission to probe, start or install services. Even
listing Fleet may initialize its config; offline fixtures must not invoke it.
