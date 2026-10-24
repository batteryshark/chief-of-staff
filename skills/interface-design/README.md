# Interface-design skills

First-party `norman` and `norman-audit`, from batteryshark's agent-kit,
`skills/development/interface-design/`, source commit
`05df7f1287b7ff26dfb51624329e6812aa1e4247`.
Principal confirmed ownership for public inclusion (KIT-NORMAN-20261023).
Source root LICENSE is MIT, copyright (c) 2026 batteryshark; a complete copy is
included in each self-contained package. Original SKILL.md, agents, references,
bin and scripts are unchanged. No private repository URL or local path is needed.

Normal kit installation installs both packages into each selected host's skills
directory. Leads may use them; workers retain their ordinary coding skill discovery.
Chief's trimmed allowlist does not include them. Interface work uses norman during
building and norman-audit before acceptance; UI worker briefs name both.

Bins use uv when available, otherwise Python3. No dependency is downloaded by the
kit installer. Skill content is not run at installation. `interface_skills.py`
refuses foreign or modified targets; uninstall removes only verified owned files.
