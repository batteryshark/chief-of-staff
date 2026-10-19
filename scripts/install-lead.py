#!/usr/bin/env python3
"""Install just a lead and its checkpoint. No chief profile, memory or services."""
import os
from pathlib import Path
import sys
import tempfile

from render import expand, lead_prompt, load_lead_config, read
from install_paths import DestinationRoot
from courtesy import skill, target as skill_target, MARKER
from courtesy_owned import OwnedSkills


def main(config_path, mode, hosts):
    config, values = load_lead_config(config_path)  # Validate before any writes.
    name = config['agent']
    destination = DestinationRoot(os.environ['HOME'])
    home = destination.path
    checkpoint_name = values['CHECKPOINT_NAME']
    marker = f'managed by chief-of-staff/install.sh; standalone lead {name}'
    prompt = lead_prompt(values)
    checkpoint = expand(read('kits/lead/skills/checkpoint.md'), values)
    outputs = []
    for host in dict.fromkeys(hosts):
        if host == 'opencode':
            outputs.extend([
                (home / f'.config/opencode/agents/{name}.md',
                 expand(read('kits/lead/hosts/opencode.md'), {**values, 'PROMPT': prompt, 'MARKER': f'<!-- {marker} -->'}) + '\n'),
                (home / f'.config/opencode/commands/{checkpoint_name}.md',
                 f'---\ndescription: Checkpoint this lead\nagent: {name}\n---\n<!-- {marker} -->\n\n{checkpoint}\n\nArguments: $ARGUMENTS\n')])
        elif host in ('claude', 'codex'):
            suffix = 'claude.md' if host == 'claude' else 'codex.toml'
            if host == 'codex' and "'''" in prompt:
                raise ValueError('prompt cannot be embedded in TOML')
            target = home / (f'.claude/agents/{name}.md' if host == 'claude' else f'.codex/{name}.config.toml')
            outputs.append((target, expand(read(f'kits/lead/hosts/{suffix}'),
                           {**values, 'PROMPT': prompt, 'MARKER': f'<!-- {marker} -->' if host == 'claude' else '# ' + marker}) + '\n'))
            outputs.append((home / f'.{host}/skills/{checkpoint_name}/SKILL.md',
                            f'---\nname: {checkpoint_name}\ndescription: Checkpoint this lead\n---\n<!-- {marker} -->\n\n{checkpoint}\n'))
        elif host not in ('home', 'bin'):
            raise ValueError('unsupported standalone host')
        if host in ('opencode', 'claude', 'codex'):
            outputs.append((skill_target(home, host), skill().replace(MARKER, f'<!-- {marker}; upstream-courtesy -->')))
    # No chief seeds or helper executables. Preflight all outputs before writing.
    destination.validate_all(target for target, _ in outputs)
    courtesy_outputs = {p: t for p, t in outputs if p.name == 'SKILL.md' and p.parent.name == 'upstream-courtesy'}
    owned = OwnedSkills(home, courtesy_outputs, owner='standalone:' + name, share_default=True) if mode != 'print' else None
    for target, _ in outputs:
        courtesy = target.name == 'SKILL.md' and target.parent.name == 'upstream-courtesy'
        if courtesy:
            continue
        owned_markers = (f'<!-- {marker} -->', f'# {marker}\n')
        if target.is_symlink() or (target.exists() and not any(m in target.read_text() for m in owned_markers)):
            raise ValueError(f'not owned by this standalone lead: {target}')
    if mode == 'install': owned.install()
    elif mode == 'uninstall': owned.uninstall()
    for target, text in outputs:
        if target in courtesy_outputs and mode != 'print':
            continue
        if mode == 'print':
            print(f'=== {target}\n{text}')
        elif mode == 'dry':
            print(f'would write {target}')
        elif mode == 'uninstall':
            if target.exists():
                target.unlink()
                print(f'removed {target}')
        elif mode == 'install':
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as f:
                temp = Path(f.name)
                f.write(text)
            try:
                temp.replace(target)
            finally:
                if temp.exists():
                    temp.unlink()
            print(f'installed {target}')
        else:
            raise ValueError('invalid install mode')


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2], sys.argv[3:])
    except (ValueError, KeyError, OSError, TypeError) as e:
        sys.exit(f'install.sh: {e}')
