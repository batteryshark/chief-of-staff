# Chief-only maintained Claude bridge

Opt-in local overlay, not a replacement for stock Claude. No global provider,
agent, model, permission or role changes. The lock records the real source commit,
Git tree, stable upstream base/release and SHA-256 of `bun.lock`; options target
only `chief-of-staff`. Native V2 discovers the built **`dist/` directory**.
MIT attribution remains in the source. This kit does not publish anything.

## Prepare without activation

Prerequisites: Git, Node >=18, Python >=3.9 and an existing Bun (tested 1.4.4),
registry connectivity or a populated Bun dependency cache, and disk space for a
full source/dependency copy. No Bun installer runs. Use `--bun /existing/bun`
if it is not on PATH. Preparation clones into a fresh staging directory, checks
the exact commit/tree/lock, runs `bun install --frozen-lockfile --ignore-scripts`,
verifies SDK **0.3.224**, explicitly runs `bun run build`, then the offline
`bun test/run.ts` suite. It never relies on Git npm `prepublishOnly`, floating
npm resolution, a live inference test, or the original checkout's `dist`.

```sh
./install.sh --chief-bridge prepare --bun /existing/bun
```

Until the approved branch is published, remote preparation fails cleanly (no
ready revision or config write). Initial rollout can instead clone a bounded,
owned, clean local source repository at the **same real production pin**:

```sh
./install.sh --chief-bridge prepare --bun /existing/bun --source-repo /owned/source
```

Local source must match HEAD, tree and lock exactly, with no tracked/untracked
changes; it is read, never edited. Preparation always builds its own clone.
Ready directories are revision-specific under
`~/.local/share/chief-of-staff/bridge/revisions/<commit>`; older revisions remain.
A ready receipt verifies repeat preparation and detects dist/source/lock drift.
Failures retain isolated staging evidence and do not replace a ready revision.
Use `--managed /owned/path` to choose another persistent root.

The prepare result exposes `runtime.path` and version using the fork's actual
`executable-path` resolver with version-only probes. **SDK dependency pinning does
not pin the executable**: an installed Claude CLI may win over the bundled SDK
executable. The receipt describes this shell environment, not necessarily the
running host. If the resolver returns null, the SDK chooses its bundled runtime;
its actual path/version still needs host verification. Save prepare stdout as
private rollout evidence and independently confirm host resolution before use.
No global environment/executable changes are made.

## Explicit parent release and fresh quiet window

The custom SDK base omits preset-only git snapshot and auto-memory-directory
guidance. Independent CLAUDE/settings-permitted memory contents and the existing
dynamic date/environment injection remain. Do not represent this as full preset
equivalence. The operator must accept that limitation, verify the actual runtime,
then request a **new** chief quiet window. Preparation/checking is not permission
to activate; first install still needs the parent's explicit release/notice.

Existing chief-local JSON config is required. JSONC is deliberately refused rather
than losing comments. No config auto-creation/global fallback. Review the plan:

```sh
./install.sh --chief-bridge plan \
  --config "$HOME/.chief-of-staff/.opencode/opencode.json" --plan /private/bridge-plan.json
# ONLY after parent release in the fresh quiet window:
./install.sh --chief-bridge activate --plan /private/bridge-plan.json \
  --receipt /private/bridge-activation.json --parent-release-quiet-window
```

Plans/receipts are absent-only mode-0600 files containing exact config bytes;
keep them private, outside source control. Activation checks ownership, symlinks,
hardlinks, prepared integrity and the exact preimage. It preserves every unrelated
config value and stock plugin entry, adding only the owned overlay entry.
Whitespace may normalize on the first JSON merge. Existing unowned overlays are
refused. For a later kit revision, pass `--previous /private/bridge-activation.json`
to `plan`; the prior owned postimage and unique overlay entry must match. Repeating
the same revision through its receipt is a no-op. Changed configs stop, never merge
silently. All receipts must have distinct absent paths.

Rollback/uninstall removes only that delta and restores exact original bytes,
only against the expected postimage:

```sh
./install.sh --chief-bridge rollback --plan /private/bridge-activation.json \
  --receipt /private/bridge-rollback.json --parent-release-quiet-window
```

No stock `stopProxy`, service restart, or deletion of old managed revisions.
Parent owns host readback, same-Location other-agent isolation, actual chief-tool
checks and matched inference/cache measurements. No automatic reload is requested.

## Ordinary finite maintenance

```sh
./install.sh --chief-bridge-check --bun /existing/bun
# Initial unpublished source can also be supplied explicitly:
./install.sh --chief-bridge-check --bun /existing/bun --source-repo /owned/source
```

Ordinary technical/OpenCode installation invokes this same check before legacy
role writes; use the dedicated entrypoint to avoid reinstalling roles. Existing
legacy role-activation guards still apply. Other hosts/profiles and ordinary
`--dry-run`, `--print`, `--uninstall` never invoke it. Every dedicated bridge action
also accepts `--dry-run`: print only, no fetch/install/build/write.

The check compares official named GitHub latest stable release with npm latest;
disagreement, missing metadata or timeout fails closed (15-second HTTP/90-second
Git timeouts). No new release means no clone or build and no Bun requirement.
A new release prepares an isolated candidate branch at the exact upstream tag,
replays the reviewed base-to-pin commits, then frozen-builds/tests it. Conflict,
SDK drift or failed checks produces a retained `candidates/*/report.json`, nonzero
exit, and leaves the lock, installed pin and all live configs untouched. No force
push, conflict resolution, watcher, automatic promotion or deployment. Candidate
reports include a proposed lock, not an installed lock. Parent must review/scan,
integrate tested replay without rewriting published history, and authorize a new
quiet window for promotion. A candidate does not carry a ready activation receipt.

## Approved Sol/medium route upkeep

```sh
./install.sh --chief-bridge routes-plan \
  --config "$HOME/.chief-of-staff/runway/routes.json" --plan /private/routes-plan.json
# ONLY after parent approval/release:
./install.sh --chief-bridge routes-apply --plan /private/routes-plan.json \
  --receipt /private/routes-activation.json --parent-release-quiet-window
./install.sh --chief-bridge rollback --plan /private/routes-activation.json \
  --receipt /private/routes-rollback.json --parent-release-quiet-window
```

The scoped helper deep-copies the actual `gpt-strong` route, retaining all account,
source, quota/window, pool/cap/reserve and unknown operator fields. Only ID, medium
variant, implementation-only categories and priority (+1) differ. No added
allowance: both routes count against the existing shared pool. Implement chooses
medium ahead of that otherwise identical high route; hard stays high. Other
providers still follow existing headroom/burn policy. Existing unequal `gpt-mid`
is refused, not overwritten. No quiescent cleanup or unrelated route repair.

Offline scoped verification:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tests python3 -B -m unittest test_chief_bridge test_routing test_usage -v
bash -n install.sh
```
