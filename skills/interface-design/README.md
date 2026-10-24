# Interface-design skills

First-party `norman` and `norman-audit`, from batteryshark's agent-kit,
`skills/development/interface-design/`, source commit
`05df7f1287b7ff26dfb51624329e6812aa1e4247`.
Principal confirmed ownership for public inclusion (KIT-NORMAN-20261023).
Source root LICENSE is MIT, copyright (c) 2026 batteryshark; a complete copy is
included in each self-contained package. Original skill bodies, agents, references,
bin and scripts are unchanged; discovery frontmatter is explicit-only. No private
repository URL or local path is needed.

Normal kit installation installs both packages into each selected host's skills
directory. Leads may use them; workers retain their ordinary coding skill discovery.
Chief's trimmed allowlist does not include them. This is an optional pack, not a role
mandate. A human-interface brief author can select `Pack: interface-design` — load
norman while building and norman-audit before the agreed acceptance check. Explicitly
naming either skill or a user request also selects that member. No role or UI keyword
selects it automatically; faithful remakes and debug/test pages imply no selection.
Functional checks remain required whether or not the pack is selected.

Explicit-only `opencode/autoinvoke: false` metadata may hide these members from the
skill tool catalog. When named, read the installed package directly with the normal
file reader: `~/.config/opencode/skills/norman/SKILL.md` and
`~/.config/opencode/skills/norman-audit/SKILL.md`. This is explicit loading, not a hook.

Bins use uv when available, otherwise Python3. No dependency is downloaded by the
kit installer. Skill content is not run at installation. `interface_skills.py`
refuses foreign or modified targets; uninstall removes only verified owned files.
