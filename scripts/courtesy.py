"""Portable skill rendered from the practice's single canonical body."""
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
NAME = 'upstream-courtesy'
MARKER = '<!-- managed by chief-of-staff/install.sh; upstream-courtesy -->'
DESCRIPTION = ('Use when preparing or sending an upstream issue, bug report, comment, patch, '
               'PR or follow-up to someone else\'s project; not internal bug fixes. '
               'Prepare a concise private draft with real proof; ask the principal/user before posting.')


def body():
    return (SRC / 'practices/upstream-courtesy/body.md').read_text().strip()


def skill():
    return f'---\nname: {NAME}\ndescription: {DESCRIPTION}\n---\n{MARKER}\n\n{body()}\n'


def target(home, host):
    prefix = '.config/opencode' if host == 'opencode' else '.' + host
    return home / prefix / 'skills' / NAME / 'SKILL.md'


def preflight(home, hosts):
    from courtesy_owned import OwnedSkills
    return OwnedSkills(home, {target(Path(home), h): skill() for h in dict.fromkeys(hosts)
                              if h in ('opencode', 'claude', 'codex')})


if __name__ == '__main__':
    import os
    import sys
    try:
        if sys.argv[1:] == ['--render']:
            sys.stdout.write(skill())
        else:
            mode, *hosts = sys.argv[1:]
            owned = preflight(os.environ['HOME'], hosts)
            if mode == 'install':
                owned.install()
            elif mode == 'uninstall':
                owned.uninstall()
    except (ValueError, OSError) as e:
        sys.exit(str(e))
