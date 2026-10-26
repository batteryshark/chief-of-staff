# Chief of staff

<img src="assets/workstack-mark.png" alt="Chief of staff project-folder mascot" width="180">

Chief of staff is an agent kit for coordinating several projects. It provides reusable coordinator and project-lead instructions, durable file-based memory, project-scoping workflows and checkpointing so decisions survive beyond a conversation. The coordinator keeps priorities and open questions; each lead owns an agreed project outcome and its verification.

## Requirements

- Bash and Python 3.10+ for rendering and installation.
- A separately installed agent host with model access: OpenCode/OpenChamber, Claude Code, Codex or Pi.
- Optional routing plugin: Node.js 22+, npm and a configured quota source.
- Pi: Node.js 22.19.0+ and a configured model; see [Pi setup](docs/pi.md).

Host capabilities differ. OpenCode/OpenChamber provides the external-session dispatch integration; other hosts receive role instructions and supported workflows. The installer does not provision model accounts or background services.

## Install

```sh
git clone https://github.com/batteryshark/chief-of-staff.git
cd chief-of-staff
./install.sh --print opencode
./install.sh --dry-run opencode
./install.sh opencode
```

Select `chief-of-staff` in your host's agent selector. Installation creates role, command and skill files under `~/.config/opencode` and seeds memory under `~/.chief-of-staff`. It does not start the host. Existing unowned files are skipped or refused.

Other host presets:

```sh
./install.sh claude
./install.sh codex
./install.sh --profile pi --dry-run
./install.sh --profile pi
```

Claude files go under `~/.claude`; Codex fragments and skills go under `~/.codex` and must be connected using your Codex version's configuration. Pi resources go under `~/.pi/agent`.

## Quick start

1. Install the role for your host and select it in a new conversation.
2. Ask it to shape a project, describing the desired outcome and constraints.
3. Review the scope and plan before implementation.
4. Use the checkpoint workflow to preserve decisions and progress before starting a fresh conversation.

In Pi, start in the brief folder and invoke `/chief-of-staff`; use `/skill:chief-shape` and `/skill:chief-checkpoint`. Load the role again in each fresh conversation. Reinstalling files does not update an already-running conversation.

## Configuration

Set `CHIEF_BRIEF_DIR` to change the memory location. Configure model policy, tool access and the current-session pointer before delegation. [Local setup](docs/LOCAL-SETUP.md) covers optional routing and notification settings; fresh routing accounts are empty. Keep actual credentials, session pointers and operational records outside the repository.

The [role guide](ROLES.md) defines authority and reporting. [Kit configuration](kits/README.md) covers standalone leads and scoped profiles. [Role-context documentation](docs/role-context.md) explains tool filtering and its limits; host permissions are not a security sandbox.

## Key commands

```sh
./install.sh --dry-run opencode
./install.sh --lead-config examples/principal.json --print opencode
./install.sh --lead-config examples/principal.json opencode
./install.sh --uninstall opencode
```

Uninstall retains personal briefs and memory. `./install.sh bin` installs the optional `chief-openchamber` and `chief-portfolio` helpers in `~/.local/bin`; the desktop helper requires an installed macOS OpenChamber app. `OPENCHAMBER_APP` overrides its location.

For optional quota routing, review [routing installation](docs/routing-install.md) and [routing workflow](routing/WORKFLOW.md), then build and install:

```sh
npm ci
npm run build
./install.sh --routing opencode
```

## Documentation

- [Local configuration](docs/LOCAL-SETUP.md)
- [Roles](ROLES.md) and [kit presets](kits/README.md)
- [Pi setup](docs/pi.md)
- [Optional services](services/README.md)
- [Routing installation](docs/routing-install.md)
- [Role permissions and filtering](docs/role-context.md)
- [Notification continuation](docs/chief-nod-continuation.md)

## License

Owned code and documentation are [MIT licensed](LICENSE). See [RIGHTS.md](RIGHTS.md), [ATTRIBUTION.md](ATTRIBUTION.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Included AI-generated artwork is offered under MIT to the extent applicable, without a claim of exclusive copyright in AI output.
