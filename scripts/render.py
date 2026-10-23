#!/usr/bin/env python3
"""Explicit kit composition. No host filename heuristics; no runtime contact."""
import json
import os
from pathlib import Path
import re
import sys

SRC = Path(__file__).resolve().parent.parent
MARK = 'managed by chief-of-staff/install.sh'
STRATEGIC_SKILLS = ('delivery-outlook', 'comparative-review')
LEVELS = ('## Levels\n\nL1 principal sets authority and outcomes; L2 chief coordinates outcomes; '
          'L3 lead owns one outcome; L4 workers perform bounded jobs.\n'
          'A lead reports either to an agent session through a live pointer or directly '
          'to the principal. The principal remains authoritative.')


def read(path):
    return (SRC / path).read_text().strip()


def strategic_skill(name):
    if name not in STRATEGIC_SKILLS:
        raise ValueError('unknown strategic skill')
    header, body = read(f'kits/shared/skills/{name}.md')[4:].split('\n---\n', 1)
    return f'---\n{header}\n---\n<!-- {MARK}; edit the source there and re-run it -->\n{body}\n'


def expand(text, values):
    # Resolve nested explicit placeholders, fail closed on unknowns or cycles.
    for _ in range(12):
        if not re.search(r'{{[A-Z_]+}}', text):
            return text
        text = re.sub(r'{{([A-Z_]+)}}', lambda m: values[m[1]], text)
    raise ValueError('cyclic composition')


def pack_values(packs):
    if not isinstance(packs, list) or not packs or len(set(packs)) != len(packs):
        raise ValueError('packs must be a nonempty unique list')
    result = {}
    for name in packs:
        if name == 'life-admin':
            raise ValueError('life-admin practice is no longer shipped; select engineering or research explicitly')
        if name not in ('engineering', 'research', 'upstream-courtesy'):
            raise ValueError('unknown practice pack')
        part = json.loads(read(f'practices/{name}/lead.json'))
        for key, value in part.items():
            if key in ('DOMAIN', 'DECISION_HEADING'):
                # Engineering keeps its established log vocabulary if attached.
                result.setdefault(key, value)
                if name == 'engineering':
                    result[key] = value
            else:
                result[key] = result.get(key, '') + ('\n' if key in result else '') + value
    if not result:
        raise ValueError('on-demand practices require a domain pack alongside them')
    return result


def owner_values(owner, technical=False):
    if not isinstance(owner, dict):
        raise ValueError('owner must be explicit')
    if owner.get('mode') == 'principal' and set(owner) == {'mode', 'style'}:
        style = owner['style']
        if not isinstance(style, str) or not style.strip() or '{{' in style:
            raise ValueError('principal style must be explicit plain text')
        return dict(OWNER_NAME='the principal', OWNER_SENTENCE='The principal',
                    OWNER_SHORT='principal', OWNER_LOG='reports directly to principal',
                    OWNER='- **The principal directly.** No chief is required. Speak in outcomes, '
                          'not mechanics. Principal style: ' + style,
                    PRINCIPAL_UPDATE='Reply here; no chief notification is required.',
                    DELIVERY='To escalate, ask the principal directly in this conversation. '
                             'Use their style: outcomes, not mechanics. Ask only when a decision '
                             'is needed; record blocked work and continue independent work.')
    if owner.get('mode') != 'agent' or set(owner) != {'mode', 'pointer', 'label'}:
        raise ValueError('owner must be principal (style) or agent (pointer, label)')
    pointer, label = owner['pointer'], owner['label']
    if (not isinstance(pointer, str) or not Path(pointer).is_absolute()
            or any(x in pointer for x in ('\n', '`', '{{'))):
        raise ValueError('owner pointer must be an absolute path')
    if not isinstance(label, str) or not re.fullmatch(r'[A-Za-z][A-Za-z -]{0,60}', label):
        raise ValueError('invalid owner label')
    if technical:
        return dict(OWNER_NAME='the chief', OWNER_SENTENCE='The chief', OWNER_SHORT='chief',
                    OWNER_LOG=f'chief: see {pointer}',
                    OWNER=f'- **The chief of staff.** Read its current session id from `{pointer}` every time\n'
                           '  you send it something, because the chief can move to a fresh session. Decisions, approvals, principal hands,\n'
                           '  continue-or-shelve requiring an answer and results needing principal review/response NOW go there; routine status stays in your project Note or inbox.\n'
                           '  The declared chief inbox is `{{BRIEF_DIR}}/inbox/` (plain files only).',
                    PRINCIPAL_UPDATE='Log already-decided principal instructions quietly in your own Note or chief inbox; message only for an actual answer or review/response needed NOW.',
                    DELIVERY='To escalate, make one `session.send` to the chief session (the id in `chief.json`) with\n'
                             '`returnResult: false` normally. Write it so\nthe chief can pass it to the principal in two spoken sentences:')
    return dict(OWNER_NAME='the reporting agent', OWNER_SENTENCE='The reporting agent',
                OWNER_SHORT='reporting agent', OWNER_LOG=f'agent owner ({label}): see {pointer}',
                OWNER=f'- **Agent session: {label}.** Re-read `{pointer}` for every send. '
                      'Use its existing `session` and `directory` fields, never a cached id. '
                      'Send answer-needed escalations and results needing review/response NOW only; routine status stays in your project Note or an authorized chief inbox.',
                PRINCIPAL_UPDATE='Record already-decided instructions quietly; notify the reporting agent only for an actual answer or review/response needed NOW.',
                DELIVERY='To escalate, use `session.send` to the freshly resolved owner session and '
                         'directory, with `returnResult: false` normally. '
                         'Do not send an acknowledgement that creates a reply loop. Write for the '
                          'principal in outcomes, with evidence last:')


def desk_lead_values(values, home, project):
    """Retired compatibility entry: old opt-ins must never produce report routes."""
    raise ValueError('Desk reporting is retired; use your own project Note and direct owner escalations.')


OWNER_SAFETY = ('## Reporting fallback\n\nFor agent-session reporting, re-read the live pointer '
                'before every send. It must contain a nonempty `session` and absolute `directory`. '
                'If missing, invalid, ambiguous or unavailable, log the blocked escalation and ask '
                'the principal directly; never guess, title-search, impersonate an owner or silently '
                'switch targets. Uncertain delivery is not permission to resend. In principal mode '
                'reply here and log the decision; no agent pointer is needed.')


def lead_prompt(values):
    reporting = '' if values.get('OWNER_SHORT') == 'principal' else read('kits/lead/agent-reporting.md')
    values = {**LEAD_HOST_DEFAULTS, **values, 'AGENT_REPORTING': reporting, 'APPROVED_PLAN_AUTHORITY': read('kits/shared/approved-plan-authority.md'), 'LOG_TEMPLATE': (SRC / 'kits/lead/log.template.md').read_text().rstrip()}
    return expand(read('kits/lead/core.md'), values) + '\n\n' + values.get('REPORT_SAFETY', OWNER_SAFETY) + '\n\n' + read('kits/shared/docket.md') + '\n\n' + read('kits/shared/fleet.md')


LEAD_HOST_DEFAULTS = {
    'REPORT_NAME': '{{OWNER_NAME}}', 'REPORT_SENTENCE': '{{OWNER_SENTENCE}}',
    'REPORT_SHORT': '{{OWNER_SHORT}}',
    'GOAL_INTRO': 'You run in goal mode. The goal objective is the project outcome that {{OWNER_NAME}} set. Work toward it\nacross turns until it is verifiably done.',
    'WORKER_SEND': 'the `openchamber` tool\'s `session.send`: an explicit `model` and `variant`,\n  and `returnResult: true` so its result comes back to you.',
    'SELF_ID': 'echo $OPENCODE_SESSION_ID', 'QUESTION_SEND': 'openchamber tool (session.send, returnResult true)',
    'RELAY_TOOL': '`session.send`',
}


def technical_values(brief):
    profile = json.loads(read('profiles/technical/profile.json'))
    if (not isinstance(profile, dict) or set(profile) != {
            'version', 'lead_packs', 'chief_agent', 'lead_agent', 'owner'}
            or type(profile['version']) is not int or profile['version'] != 1):
        raise ValueError('invalid technical profile')
    for key in ('chief_agent', 'lead_agent'):
        if not isinstance(profile[key], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', profile[key]):
            raise ValueError('invalid profile agent name')
    if profile['chief_agent'] == profile['lead_agent']:
        raise ValueError('chief and lead names must be distinct')
    owner = {**profile['owner'], 'pointer': profile['owner']['pointer'].replace('{{BRIEF_DIR}}', brief)}
    return {**pack_values(profile['lead_packs']), **owner_values(owner, technical=True),
            'OPERATIONAL_RECORD': '',
            **json.loads(read('profiles/technical/shape.json')),
            'INTRO': read('profiles/technical/lead-intro.md'),
            'MODEL_POLICY': read('profiles/technical/model-policy.md'),
            'OPENCODE_WORKSPACE': read('practices/engineering/opencode-workspace.md'),
            'WORKER_ROUTING': 'Route models with `runway` (prepare,\n  dispatch, bind, finish) as the routing workflow at `{{RUNWAY_WORKFLOW}}` describes.',
            'BRIEF_DIR': brief, 'LEAD_AGENT': profile['lead_agent'], 'CHIEF_AGENT': profile['chief_agent'],
            'CHECKPOINT_NAME': 'checkpoint',
            'SHAPE_NAME': 'shape', 'SESSION_ID_HELP': '`echo $OPENCODE_SESSION_ID`',
            'SCOPE': read('profiles/technical/scope.md'),
            'MODELS': read('services/models/technical-chief.md'),
            'FLEET': read('services/runway/technical-chief.md'),
            'MODEL_MEMORY': '- **`models.md`**, the model policy.',
            'LEAD_START_POLICY': 'a Strong-class model with usage left\n  (see Models and usage)',
            'CHECKIN': '- **Checking in.** At EVERY catch-up read `{{BRIEF_DIR}}/inbox/` using the inbox rule below. Run `chief-portfolio` for unread count, all three status Note parts,\n  Note age (stale warnings) and lead liveness. Missing or ambiguous Notes are lead-owned\n  clarification, not inferred principal actions. For private triage use `--private` or read LEAD.md\n  and open.md, not worker sessions; never relay raw tracking labels to the principal.\n  Leads own their Notes; no routine chief or desk status pings.',
            'RUNWAY_WORKFLOW': str(SRC / 'routing/WORKFLOW.md'),
            'HOME_INFRA': str(Path.home() / '.local/share/chief-of-staff/home-infra.md')}


# Each managed template declares its prompt and workflow explicitly.
TEMPLATES = {
    'hosts/opencode.md': ('chief', None),
    'hosts/claude-agent.md': ('chief', None),
    'hosts/claude-output-style.md': ('chief', None),
    'hosts/codex.config.toml': ('chief', None),
    'hosts/opencode-lead.md': ('lead', None),
    'hosts/claude-lead-agent.md': ('lead', None),
    'hosts/codex-lead.config.toml': ('lead', None),
}
for workflow in ('shape', 'checkpoint'):
    for host in ('opencode-command.md', 'skill.md', 'codex-openai.yaml'):
        TEMPLATES[f'workflows/{workflow}/hosts/{host}'] = (None, workflow)
for path in ('scripts/chief-openchamber', 'scripts/chief-portfolio', 'scripts/nod-alert', 'scripts/chief-nod', 'scripts/chief-images-server',
             'services/home/reference.md', 'models.md',
             'kits/chief/memory/AGENTS.md', 'kits/chief/memory/CLAUDE.md',
             'kits/chief/memory/open.md', 'kits/chief/memory/principal.md', 'kits/chief/memory/chief.json'):
    TEMPLATES[path] = (None, None)


def desk_checkpoint(workflow, home, project):
    """Retired compatibility entry; never render historical handover routes."""
    raise ValueError('Desk reporting is retired; use the ordinary lead checkpoint.')


def render(template, brief, desk_project=None):
    if template == 'services/role-context.mjs':
        from role_context import exposure_policy
        source = read(template).replace("import {readFileSync} from 'node:fs';\n", '')
        return source.replace(
            "const policy = JSON.parse(readFileSync(new URL('./role-policy.json', import.meta.url), 'utf8'));",
            'const policy = ' + json.dumps(exposure_policy()) + ';') + '\n'
    if template.startswith('reset-procedure:'):
        from lean_roles import procedures
        return procedures(brief)[template.split(':', 1)[1]]
    if template == 'kits/chief/memory/AGENTS.md':
        return f'<!-- {MARK}; edit the source there and re-run it -->\n' + read('kits/reset/AGENTS.md') + '\n'
    if template in (f'kits/shared/skills/{name}.md' for name in STRATEGIC_SKILLS):
        return strategic_skill(Path(template).stem)
    if template == 'skills/upstream-courtesy/SKILL.md':
        from courtesy import skill
        return skill()
    role, workflow = TEMPLATES[template]
    values = technical_values(brief)
    values['DIRECTORY_GUIDE'] = str(Path(brief) / '.kit-resources/services/directory/README.md')
    values['SERVICE_GUIDE'] = str(Path(brief) / '.kit-resources/services/README.md')
    values['SERVICE_RESOURCES'] = str(Path(brief) / '.kit-resources')
    from service_resources import resource_paths
    rules = []
    for prefix in (values['SERVICE_RESOURCES'] + '/*', '.kit-resources/*'):
        for action in ('read', 'edit'):
            rules.append((action, prefix, 'deny'))
    for file in resource_paths(brief):
        for resource in (str(file), str(file.relative_to(brief))):
            rules.append(('read', resource, 'allow'))
    values['RESOURCE_PERMISSIONS'] = '\n'.join(
        f'  - action: {a}\n    resource: {json.dumps(r)}\n    effect: {e}' for a, r, e in rules)
    if role in ('chief', 'lead') and desk_project is None:
        from lean_roles import render_role
        return render_role(template, role, brief)
    values['APPROVED_PLAN_AUTHORITY'] = read('kits/shared/approved-plan-authority.md')
    values['CLI_ESCALATIONS'] = read('hosts/codex-lead-escalations.md'
                                   if template == 'hosts/codex-lead.config.toml'
                                   else 'hosts/claude-lead-escalations.md')
    values['HOST_ESCALATIONS'] = ('**Escalations.** `session.send` to the chief\'s session id and directory from `chief.json`, '
                                'with `returnResult: false` normally. Include your own session/absolute project directory '
                                'and stable private question reference/scope. The real answer is explicitly targeted '
                                'to you with that reference; ignore late receipts after resolution.')
    if desk_project is not None:
        if role != 'lead' and workflow != 'checkpoint':
            raise ValueError('desk reporting opt-in applies only to lead composition')
        values = desk_lead_values(values, brief, desk_project)
    if role == 'lead':
        prompt = lead_prompt(values) + '\n\n' + read('kits/shared/home-infra.md')
    elif role == 'chief':
        core = read('kits/chief/core.md')
        chief_values = {**values,
                        **json.loads(read('profiles/technical/chief-style.json')),
                        'DEPTH_STYLE': read('profiles/technical/depth.md'),
                        'EXAMPLES': read('profiles/technical/examples.md'),
                        'INTRO': read('profiles/technical/chief-intro.md'),
                        'TONE': read('profiles/technical/tone.md')}
        prompt = expand(core, chief_values)
        prompt += '\n\n' + LEVELS + '\n\n' + read('kits/shared/docket.md') + '\n\n' + read('kits/shared/fleet.md') + '\n\n' + read('services/directory/instructions.md') + '\n\n' + read('kits/shared/home-infra.md')
    else:
        prompt = ''
    if template.endswith('.toml') and "'''" in prompt:
        raise ValueError('prompt cannot be embedded in TOML')
    marker = f'{MARK}; edit the source there and re-run it'
    values.update(PROMPT=prompt, MARKER=('# ' + marker if template.endswith(('.toml', '.yaml'))
                                      or template.startswith('scripts/') else '<!-- ' + marker + ' -->'),
                  CLAUDE_NOTES=read('hosts/claude-lead-notes.md' if role == 'lead' else 'hosts/claude-notes.md'))
    if workflow:
        values['WORKFLOW'] = (
            read('kits/reset/skills/checkpoint/SKILL.md').split('\n---\n', 1)[1].strip()
            if workflow == 'checkpoint' else read('kits/chief/skills/shape/workflow.md'))
        if workflow == 'checkpoint' and desk_project is not None:
            values['WORKFLOW'] = desk_checkpoint(values['WORKFLOW'], brief, desk_project)
        if workflow == 'shape':
            values['TEMPLATE'] = read('kits/chief/skills/shape/PROJECT.template.md')
    return expand((SRC / template).read_text(), values)


def load_lead_config(path):
    config = json.loads(Path(path).read_text())
    if (not isinstance(config, dict) or set(config) != {'version', 'agent', 'packs', 'owner'}
            or type(config['version']) is not int or config['version'] != 1):
        raise ValueError('lead config requires version=1, agent, packs, owner only')
    if not isinstance(config['agent'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', config['agent']):
        raise ValueError('invalid agent name')
    if config['agent'] in ('lead', 'chief-of-staff', 'shape', 'checkpoint'):
        raise ValueError('standalone agent must not collide with technical defaults')
    values = {**pack_values(config['packs']), **owner_values(config['owner']),
              'INTRO': 'You are the lead for one outcome. Own its plan, bounded workers, decisions, '
                       'verification and log. The principal is authoritative. Keep the agreed outcome intact.',
              'MODEL_POLICY': '## Optional shared policy\n\nUse an explicitly supplied model policy or routing service if available. '
                              'No chief memory is required. Without one, choose an available model within '
                              'current permissions. Paid use requires explicit project approval. '
                              'Checkpoint before moving a worker; never silently lower the lead quality tier.',
              'WORKER_ROUTING': 'Use a supplied routing service if configured; otherwise choose an available authorized model.',
              'LEAD_AGENT': config['agent'], 'CHECKPOINT_NAME': config['agent'] + '-checkpoint'}
    return config, values


if __name__ == '__main__':
    try:
        sys.stdout.write(render(sys.argv[1], sys.argv[2]))
    except (ValueError, KeyError, OSError, TypeError) as e:
        sys.exit(f'install.sh: {e}')
