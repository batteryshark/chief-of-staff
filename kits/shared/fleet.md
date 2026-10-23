## Shared services: Fleet

On macOS, every background service a lead installs must be registered in Fleet in the same
step using `fleet add` or `fleet adopt`, with port, health probe and group, so the
principal can list/start/stop it centrally. Read the configured Fleet checkout's `README.md`;
the registry is `~/.config/fleet/services.json`. Registration is necessary, not
permission to install: the approved initial project plan may already authorize the service;
do not ask again when covered. Outside that authority, resolve coverage before proceeding.
Check the operator's existing registry before adopting a service; avoid duplicate
adoption. This check grants no permission to probe, start or install services.
