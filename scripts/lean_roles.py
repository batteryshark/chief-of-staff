"""Canonical lean role output, explicit-load skills and full kit prose accounting."""
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
MARK = '<!-- managed by chief-of-staff/install.sh; lean role -->'
LIMITS = {'chief': (150, 1600), 'lead': (100, 1200)}
PROCEDURES = {
    'worker-dispatch': 'kits/reset/skills/worker-dispatch/SKILL.md',
    'worktree-safety': 'kits/reset/skills/worktree-safety/SKILL.md',
    'dispatch-events': 'kits/reset/skills/dispatch-events/SKILL.md',
    'checkpoint': 'kits/reset/skills/checkpoint/SKILL.md',
    'reporting': 'kits/reset/skills/reporting/SKILL.md',
    'delivery-outlook': 'kits/shared/skills/delivery-outlook.md',
    'comparative-review': 'kits/shared/skills/comparative-review.md',
}
CATALOG_SOURCES = {
    'checkpoint': 'workflows/checkpoint/hosts/skill.md',
    'shape': 'workflows/shape/hosts/skill.md',
    'delivery-outlook': 'kits/shared/skills/delivery-outlook.md',
    'comparative-review': 'kits/shared/skills/comparative-review.md',
}


def description(text):
    return re.search(r'^description: (.+)$', text, re.M)[1]


def catalog():
    # Include the existing kit catalog, even though the new reset procedures
    # deliberately add NO catalog entries (autoinvoke:false, explicit IDs).
    from courtesy import DESCRIPTION
    result = {name: description((ROOT / path).read_text()) for name, path in CATALOG_SOURCES.items()}
    result['upstream-courtesy'] = DESCRIPTION
    tool = (ROOT / 'routing/plugin.js').read_text()
    result['runway'] = re.search(r"description:'([^']+)'", tool)[1]
    result['runway.request'] = re.search(r"\.describe\('([^']+)'\)", tool)[1]
    return result


def catalog_text(entries):
    # Audit all model-facing id/name/description prose, normally wrapped, not
    # one packed line per skill. Markup itself is not extra instruction prose.
    return '\n'.join(line for name, desc in sorted(entries.items())
                     for line in textwrap.wrap(f'{name} ({name}): {desc}', 110)) + '\n'


def body(role, brief):
    return (ROOT / f'kits/reset/{role}.md').read_text().replace('{{BRIEF_DIR}}', brief)


def installed_startup(location):
    """Inventory kit-owned AGENTS prose on the real upward-discovery path."""
    location = Path(location).resolve()
    paths = [Path.home() / '.config/opencode/AGENTS.md']
    for directory in (location, *location.parents):
        paths.append(directory / 'AGENTS.md')
        if directory == Path.home():
            break
    texts = []
    for path in dict.fromkeys(paths):
        if path.is_file():
            text = path.read_text()
            if 'managed by chief-of-staff/install.sh' in text:
                texts.append(text)
    return '\n'.join(texts)


def budget(role, text, brief, entries=None, startup=None, header_prose=''):
    entries = catalog() if entries is None else entries
    if startup is None:
        startup = ('<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->\n'
                   + (ROOT / 'kits/reset/AGENTS.md').read_text()) if role == 'chief' else ''
    parts = [text, header_prose, startup, catalog_text(entries)]
    lines = sum(len(p.splitlines()) for p in parts)
    words = sum(len(p.split()) for p in parts)
    caps = LIMITS[role]
    if lines > caps[0] or words > caps[1]:
        raise ValueError(f'{role} full kit prose exceeds budget: {lines} lines / {words} words')
    # A single expanded filesystem path may be wide, but is never squeezed prose.
    for line in text.splitlines():
        # Long user-selected absolute paths are not packed instruction prose.
        readable = re.sub(r'`/[^`]+`', '`PATH`', line)
        if len(readable) > 110:
            raise ValueError(f'{role} packed/overwide prose: {line}')
    if '\t' in text:
        raise ValueError('tabs in instruction prose')
    return {'lines': lines, 'words': words, 'catalog_lines': len(catalog_text(entries).splitlines()),
            'startup_lines': len(startup.splitlines())}


def render_role(template, role, brief):
    if template in ('hosts/opencode.md', 'hosts/opencode-lead.md'):
        from role_contract import agent
        return agent(role, str(Path.home()), brief)
    text = body(role, brief)
    # Native OpenCode has explicit skill IDs. Other hosts get stable plain read
    # paths, outside their auto-discovered catalogs; no unsupported metadata guess.
    if not template.startswith('hosts/opencode'):
        directory = Path.home() / '.local/share/chief-of-staff/reset'
        text = f'Read triggered reset-*.md files under `{directory}/`.\n' + text
    if template.startswith('hosts/codex'):
        if role == 'lead':
            text = text.replace('Run in goal mode.',
                                'Pursue the whole approved outcome across turns; Codex has no native goal mode.\n')
        budget(role, MARK + '\n' + text, brief)
        if "'''" in text:
            raise ValueError('unsafe TOML instruction embedding')
        return f"# managed by chief-of-staff/install.sh; lean role\ndeveloper_instructions = '''\n{MARK}\n{text}'''\n"
    header = (ROOT / template).read_text()[4:].split('\n---\n', 1)[0]
    header = re.sub(r'^description:.*$', f'description: {role.capitalize()}.', header, flags=re.M)
    for key, value in {'BRIEF_DIR': brief, 'RUNWAY_WORKFLOW': str(ROOT / 'routing/WORKFLOW.md'),
                       'HOME_INFRA': str(Path.home() / '.local/share/chief-of-staff/home-infra.md')}.items():
        header = header.replace('{{' + key + '}}', value)
    if '{{' in header:
        raise ValueError('unresolved role metadata')
    prose = '\n'.join(line for line in header.splitlines() if line.startswith(('name:', 'description:')))
    startup = None
    if template.startswith('hosts/claude') and role == 'chief':
        startup = ('<!-- managed by chief-of-staff/install.sh; edit the source there and re-run it -->\n'
                   + (ROOT / 'kits/reset/AGENTS.md').read_text()
                   + '<!-- managed by chief-of-staff/install.sh -->\n@AGENTS.md\n')
    budget(role, MARK + '\n' + text, brief, header_prose=prose, startup=startup)
    return '---\n' + header + '\n---\n' + MARK + '\n' + text


def procedures(brief):
    from render import render
    from courtesy import skill
    sources = {name: (ROOT / path).read_text() for name, path in PROCEDURES.items()}
    sources['shape'] = render('workflows/shape/hosts/skill.md', brief)
    sources['upstream-courtesy'] = skill()
    result = {}
    for name, source in sources.items():
        content = source.split('\n---\n', 1)[1].strip()
        if name == 'worker-dispatch':
            for guide in ('kits/shared/docket.md', 'kits/shared/fleet.md'):
                content += '\n\n' + (ROOT / guide).read_text().strip()
        if name == 'reporting':
            content += f'\n\nThe configured chief pointer is `{brief}/chief.json`; validate it before every send.\n'
        content = content.replace("the kit's routing/WORKFLOW.md", '`' + str(ROOT / 'routing/WORKFLOW.md') + '`')
        content = content.replace("the kit's docs/chief-nod-continuation.md",
                                  '`' + str(ROOT / 'docs/chief-nod-continuation.md') + '`')
        ident = 'reset-' + name
        result[ident] = ('---\nname: ' + ident + '\ndescription: Explicit on-demand procedure.\n'
                         'metadata:\n  opencode/autoinvoke: false\n---\n'
                         '<!-- managed by chief-of-staff/install.sh; reset procedure -->\n' + content + '\n')
    return result
