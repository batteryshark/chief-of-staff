#!/usr/bin/env bash
# Install or update the chief-of-staff and lead agent profiles, the chief's workflows
# (workflows/*) and the chief-openchamber command for OpenCode/OpenChamber, Claude Code and Codex.
#
#   ./install.sh                     install or update every host
#   ./install.sh opencode claude     only these hosts (opencode, claude, codex, bin, home)
#   ./install.sh --routing opencode install the built quota tool and OpenCode agent
#   ./install.sh --uninstall [hosts] remove the files this script installed
#   ./install.sh --dry-run [hosts]   show what would change
#   ./install.sh --role-fixture ROOT [--location PATH] stage repair-owned role fixture only
#   ./install.sh --shell-policy LOCATION [--dry-run] exclude only the unsafe shell wrapper in one Location
#   ./install.sh --role-binding LOCATION [--dry-run] install own-memory/exact Knowledge-plan permissions only
#   ./install.sh --role-fleet --docket-source PATH [--include-location PATH] [--dry-run] coordinated lead migration
#   ./install.sh --ordinary-call-maintenance LOCATION --revision NAME [--dry-run] refresh only an existing owned entry
#   ./install.sh --print <host>      print the rendered file(s) for a host
#   ./install.sh --chief-permissions-only [--dry-run]  preserve prompt, repair chief edit rules
#   ./install.sh --chief-body-only --revision NAME --expected-sha256 SHA [--local] [--dry-run]
#     fixed global/canonical local chief body only; exact frontmatter preserved;
#     watched replacement may invalidate global Locations or the chief Location;
#     coordinate the window first. No explicit reload/restart or policy updates.
#   ./install.sh --profile technical same legacy defaults (also the no-argument default)
#   ./install.sh --profile example   scoped local OpenCode/home bundle
#   ./install.sh --profile <JSON>    another domain using the explicit scoped manifest
#   ./install.sh --profile pi       Pi 1.0 Chief and included lead prompt/skills
#   ./install.sh --candidate-config <JSON>  absent-only local OpenCode proof clone
#   ./install.sh --reset-pilot <JSON>  unique scoped lean role; --uninstall archives its bundle
#   ./install.sh --profile pi --pi-capability pi-subagents --pi-capability pi-goal-x
#
# Each host file is rendered through scripts/render.py's explicit kit/template manifest,
# plus a template in hosts/, or from a workflow's
# workflow.md and PROJECT.template.md plus a template in workflows/<name>/hosts/. Every file is a
# generated copy, because every host needs its own frontmatter or TOML wrapper. Rendered files
# carry a marker line. A file without the marker is never overwritten or removed. The brief
# directory (CHIEF_BRIEF_DIR, default ~/.chief-of-staff) is created with a seed brief if missing
# and is never removed. Uninstall also removes a workflow's skill directory once it is empty.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ${1:-} == --chief-body-only ]]; then
  shift
  exec python3 "$SRC/scripts/install-chief-permissions.py" "${CHIEF_BRIEF_DIR:-$HOME/.chief-of-staff}" "$HOME" --body-only "$@"
fi
if [[ ${1:-} == --ordinary-call-maintenance ]]; then
  shift
  exec python3 "$SRC/scripts/install-ordinary-call.py" "$@"
fi
if [[ ${1:-} == --role-fleet ]]; then
  shift
  exec python3 "$SRC/scripts/install-role-fleet.py" "$@"
fi
if [[ ${1:-} == --role-binding ]]; then
  shift
  exec python3 "$SRC/scripts/install-role-binding.py" "$@"
fi
if [[ ${1:-} == --shell-policy ]]; then
  shift
  exec python3 "$SRC/scripts/install-shell-policy.py" "$@"
fi
if [[ ${1:-} == --role-fixture ]]; then
  shift
  exec python3 "$SRC/scripts/install-role-fixture.py" "$@"
fi
BRIEF_DIR="${CHIEF_BRIEF_DIR:-$HOME/.chief-of-staff}"
MARK="managed by chief-of-staff/install.sh"
LEGACY_MARK="managed by orchestra-next/agents/chief-of-staff/install.sh"

mode=install; hosts=(); routing=false; lead_config=""; candidate_config=""; profile="technical"; pi_caps=()
chief_permissions_only=false
reset_pilot=""
while (($#)); do
  case "$1" in
    --reset-pilot) shift; reset_pilot="${1:?--reset-pilot requires a manifest}" ;;
    --chief-permissions-only)
      chief_permissions_only=true
      ;;
    --profile) shift; profile="${1:?--profile requires technical, example or a manifest path}" ;;
    --lead-config) shift; lead_config="${1:?--lead-config requires a JSON file}" ;;
    --candidate-config) shift; candidate_config="${1:?--candidate-config requires a JSON file}" ;;
    --pi-capability) shift; pi_caps+=("${1:?--pi-capability requires an ID}") ;;
    --routing) routing=true ;;
    --uninstall) mode=uninstall ;;
    --dry-run) mode=dry ;;
    --print) mode=print ;;
    -h|--help) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
    opencode|claude|codex|bin|home) hosts+=("$1") ;;
    *) echo "install.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
# The final matrix is no longer a per-edit gate. The legacy global migration
# still lacks enrolled project bindings and would affect a running Docket lead.
# Scoped fixes (above) can land independently; global role activation is coordinated.
if [[ $mode == install && $profile == technical && -z $lead_config && -z ${candidate_config:-} && -z $reset_pilot && $chief_permissions_only == false && ( ${#hosts[@]} == 0 || " ${hosts[*]} " == *" opencode "* ) && -f "$HOME/.config/opencode/agents/lead.md" ]] && ! grep -qF '; lean role' "$HOME/.config/opencode/agents/lead.md"; then
  echo 'Global role activation needs coordinated enrolled bindings; use scoped --shell-policy for the shell fix.' >&2
  exit 2
fi
if [[ -n $reset_pilot ]]; then
  [[ $profile == technical && -z $lead_config && -z ${candidate_config:-} && $chief_permissions_only == false && $routing == false && ${#pi_caps[@]} == 0 && ${#hosts[@]} == 0 ]] || { echo 'reset pilot cannot combine other targets' >&2; exit 2; }
  exec python3 "$SRC/scripts/install-reset-pilot.py" "$reset_pilot" "$mode"
fi
if [[ $chief_permissions_only == true ]]; then
  [[ $profile == technical && -z $lead_config && -z ${candidate_config:-} && $routing == false && ${#pi_caps[@]} == 0 && ${#hosts[@]} == 0 ]] || { echo 'permission-only mode cannot combine other targets' >&2; exit 2; }
  case "$mode" in
    install) exec python3 "$SRC/scripts/install-chief-permissions.py" "$BRIEF_DIR" "$HOME" ;;
    dry) exec python3 "$SRC/scripts/install-chief-permissions.py" "$BRIEF_DIR" "$HOME" --dry-run ;;
    *) echo 'permission-only mode supports install or dry-run only' >&2; exit 2 ;;
  esac
fi
if [[ -n $candidate_config ]]; then
  [[ $profile == technical && -z $lead_config && $routing == false && ${#pi_caps[@]} == 0 && ${#hosts[@]} == 0 ]] || { echo 'candidate mode cannot combine profiles, hosts, lead-config or routing' >&2; exit 2; }
  exec python3 "$SRC/scripts/install-candidate.py" "$candidate_config" "$mode"
fi
if [[ $profile == pi ]]; then
  [[ -z $lead_config && $routing == false && ${#hosts[@]} == 0 ]] || { echo 'Pi preset cannot combine other hosts, lead-config or routing' >&2; exit 2; }
  if ((${#pi_caps[@]})); then
    exec python3 "$SRC/scripts/install-pi.py" "$mode" "${pi_caps[@]}"
  else
    exec python3 "$SRC/scripts/install-pi.py" "$mode"
  fi
fi
if ((${#pi_caps[@]})); then echo 'Pi capabilities require --profile pi' >&2; exit 2; fi
if [[ $profile != technical ]]; then
  [[ -z $lead_config && $routing == false ]] || { echo 'scoped profiles cannot combine --lead-config or --routing' >&2; exit 2; }
  if ((${#hosts[@]})); then
    exec python3 "$SRC/scripts/install-profile.py" "$profile" "$mode" "${hosts[@]}"
  else
    exec python3 "$SRC/scripts/install-profile.py" "$profile" "$mode"
  fi
fi
((${#hosts[@]})) || hosts=(opencode claude codex bin home)
if [[ -n $lead_config ]]; then
  [[ $routing == false ]] || { echo 'standalone lead does not install routing' >&2; exit 2; }
  exec python3 "$SRC/scripts/install-lead.py" "$lead_config" "$mode" "${hosts[@]}"
fi

# Render the same canonical guide paths that the resource installer owns.
BRIEF_DIR="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$BRIEF_DIR")"

# host -> "template|target|prune-dir" lines. The template path is relative to this directory.
# prune-dir, when set, is removed on uninstall once it is empty (a workflow's skill directory).
WF=workflows/shape/hosts
CP=workflows/checkpoint/hosts
targets() {
  case "$1" in
    opencode) echo "hosts/opencode.md|$HOME/.config/opencode/agents/chief-of-staff.md|"
              echo "hosts/opencode-lead.md|$HOME/.config/opencode/agents/lead.md|"
              echo "services/role-context.mjs|$HOME/.config/opencode/plugins/chief-role-context.js|"
              echo "$WF/opencode-command.md|$HOME/.config/opencode/commands/shape.md|"
               echo "$CP/opencode-command.md|$HOME/.config/opencode/commands/checkpoint.md|"
               echo "skills/upstream-courtesy/SKILL.md|$HOME/.config/opencode/skills/upstream-courtesy/SKILL.md|$HOME/.config/opencode/skills/upstream-courtesy" ;;
    claude)   echo "hosts/claude-output-style.md|$HOME/.claude/output-styles/chief-of-staff.md|"
              echo "hosts/claude-agent.md|$HOME/.claude/agents/chief-of-staff.md|"
              echo "hosts/claude-lead-agent.md|$HOME/.claude/agents/lead.md|"
              echo "$WF/skill.md|$HOME/.claude/skills/shape/SKILL.md|$HOME/.claude/skills/shape"
               echo "$CP/skill.md|$HOME/.claude/skills/checkpoint/SKILL.md|$HOME/.claude/skills/checkpoint"
               echo "skills/upstream-courtesy/SKILL.md|$HOME/.claude/skills/upstream-courtesy/SKILL.md|$HOME/.claude/skills/upstream-courtesy" ;;
    codex)    echo "hosts/codex.config.toml|$HOME/.codex/chief-of-staff.config.toml|"
              echo "hosts/codex-lead.config.toml|$HOME/.codex/lead.config.toml|"
              echo "$WF/skill.md|$HOME/.codex/skills/shape/SKILL.md|$HOME/.codex/skills/shape"
              echo "$WF/codex-openai.yaml|$HOME/.codex/skills/shape/agents/openai.yaml|$HOME/.codex/skills/shape"
              echo "$CP/skill.md|$HOME/.codex/skills/checkpoint/SKILL.md|$HOME/.codex/skills/checkpoint"
               echo "$CP/codex-openai.yaml|$HOME/.codex/skills/checkpoint/agents/openai.yaml|$HOME/.codex/skills/checkpoint"
               echo "skills/upstream-courtesy/SKILL.md|$HOME/.codex/skills/upstream-courtesy/SKILL.md|$HOME/.codex/skills/upstream-courtesy" ;;
    bin)      echo "scripts/chief-openchamber|$HOME/.local/bin/chief-openchamber|"
              echo "scripts/chief-portfolio|$HOME/.local/bin/chief-portfolio|"
              echo "scripts/nod-alert|$HOME/.local/bin/nod-alert|"
              echo "scripts/chief-nod|$HOME/.local/bin/chief-nod|"
              echo "scripts/chief-images-server|$HOME/.local/bin/chief-images-server|"
              echo "services/home/reference.md|$HOME/.local/share/chief-of-staff/home-infra.md|$HOME/.local/share/chief-of-staff" ;;
    home)     echo "kits/chief/memory/AGENTS.md|$BRIEF_DIR/AGENTS.md|"
              echo "kits/chief/memory/CLAUDE.md|$BRIEF_DIR/CLAUDE.md|" ;;
  esac
  if [[ $1 == opencode || $1 == claude || $1 == codex ]]; then
    local base="$HOME/.$1/skills"
    [[ $1 == opencode ]] && base="$HOME/.config/opencode/skills"
    local name
    for name in delivery-outlook comparative-review; do
      echo "kits/shared/skills/$name.md|$base/$name/SKILL.md|$base/$name"
    done
    for name in worker-dispatch worktree-safety dispatch-events checkpoint reporting delivery-outlook comparative-review shape upstream-courtesy; do
      if [[ $1 == opencode ]]; then
        echo "reset-procedure:reset-$name|$base/reset-$name/SKILL.md|$base/reset-$name"
      else
        echo "reset-procedure:reset-$name|$HOME/.local/share/chief-of-staff/reset/reset-$name.md|"
      fi
    done
  fi
}

render() { # template -> stdout
  python3 "$SRC/scripts/render.py" "$1" "$BRIEF_DIR"
}

ours() { [[ -f "$1" && ! -L "$1" ]] && { grep -qF "$MARK" "$1" || grep -qF "$LEGACY_MARK" "$1"; }; }

seed() { # template -> file in the brief directory, created once and then owned by the chief
  local target="$BRIEF_DIR/$2"
  [[ -e "$target" ]] && return 0
  if [[ $mode == dry ]]; then echo "create  $target"; return 0; fi
  mkdir -p "$BRIEF_DIR/archive"
  render "$1" > "$target"
  echo "created $target"
}

seed_brief() {
  [[ -e "$BRIEF_DIR/brief.md" ]] && return 0
  if [[ $mode == dry ]]; then echo "create  $BRIEF_DIR/brief.md"; return 0; fi
  mkdir -p "$BRIEF_DIR"
  cat > "$BRIEF_DIR/brief.md" <<'EOF'
# Running brief

## Priorities

## Open threads

## Stop conditions

## Decisions

## In flight

## Parked
EOF
  echo "created $BRIEF_DIR/brief.md"
}

status=0
resources=false
for host in "${hosts[@]}"; do
  case "$host" in opencode|claude|codex|home) resources=true ;; esac
done
if [[ $resources == true && $mode != print ]]; then
  python3 "$SRC/scripts/install-resources.py" "$BRIEF_DIR" check "${hosts[@]}"
fi
# Preflight every new skill target before any mutation of the existing bundle.
if [[ $mode != print ]]; then python3 "$SRC/scripts/courtesy.py" check "${hosts[@]}"; fi
if [[ $resources == true ]]; then
  python3 "$SRC/scripts/install-resources.py" "$BRIEF_DIR" "$mode" "${hosts[@]}"
fi
# Courtesy is handled exclusively by its exact-owned absent-create helper,
# before legacy mutations; never fall through to marker-based replace/delete.
if [[ $mode == install || $mode == uninstall ]]; then
  python3 "$SRC/scripts/courtesy.py" "$mode" "${hosts[@]}"
fi
for host in "${hosts[@]}"; do
  while IFS='|' read -r tmpl target prune; do
    if [[ $tmpl == skills/upstream-courtesy/SKILL.md && $mode != print ]]; then continue; fi
    case "$mode" in
      print)
        echo "=== $target"; render "$tmpl"; echo ;;
      uninstall)
        if ours "$target"; then rm -f "$target"; echo "removed $target"
          [[ -n $prune && -d $prune ]] && find "$prune" -depth -type d -empty -delete
        elif [[ -e "$target" || -L "$target" ]]; then echo "skip    $target (not created by this script)"; status=1
        else echo "absent  $target"; fi ;;
      install|dry)
        if [[ -e "$target" || -L "$target" ]] && ! ours "$target"; then
          echo "skip    $target (exists and was not created by this script)"; status=1; continue
        fi
        new="$(render "$tmpl")"
        if [[ -f "$target" ]] && [[ "$(cat "$target")" == "$new" ]]; then echo "same    $target"; continue; fi
        verb=$([[ -f "$target" ]] && echo update || echo create)
        if [[ $mode == dry ]]; then echo "$verb  $target"; continue; fi
        mkdir -p "$(dirname "$target")"
        tmp="$(mktemp "$target.XXXXXX")"
        printf '%s\n' "$new" > "$tmp" && mv "$tmp" "$target"
        [[ $tmpl == scripts/* ]] && chmod 755 "$target"
        echo "${verb}d $target" ;;
    esac
  done < <(targets "$host")
done
if [[ $mode == install || $mode == dry ]]; then
  if [[ $mode == install ]]; then mkdir -p "$BRIEF_DIR/inbox" "$BRIEF_DIR/archive/inbox"; fi
  seed_brief
  seed models.md models.md
  seed kits/chief/memory/open.md open.md
  seed kits/chief/memory/principal.md principal.md
  seed kits/chief/memory/chief.json chief.json
fi
if [[ $routing == true ]]; then python3 "$SRC/scripts/install-routing.py" "$SRC" "$mode" || status=1; fi
exit $status
