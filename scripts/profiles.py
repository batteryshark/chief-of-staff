"""Small scoped manifest and composition; standalone lead imports none of this."""
import json
from pathlib import Path
import re

from render import SRC, LEVELS, expand, lead_prompt, read
from service_resources import resource_paths


def load_profile(selection):
    file = SRC / 'profiles/example/profile.json' if selection == 'example' else Path(selection)
    profile = json.loads(file.read_text())
    fields = {'version', 'id', 'responsibility', 'home', 'chief_agent', 'lead_agent',
              'worker_agent', 'lead_packs', 'remit', 'tone', 'adapter'}
    if not isinstance(profile, dict) or set(profile) != fields or type(profile['version']) is not int or profile['version'] != 1:
        raise ValueError('invalid scoped profile schema')
    ident = profile['id']
    if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', ident) or ident in ('technical', 'lead', 'chief-of-staff'):
        raise ValueError('invalid or reserved domain id')
    if profile['home'] != '.chiefs/' + ident:
        raise ValueError('scoped home must be .chiefs/<domain-id>')
    for key in ('chief_agent', 'lead_agent', 'worker_agent'):
        name = profile[key]
        if not isinstance(name, str) or not re.fullmatch(re.escape(ident) + r'-[a-z][a-z0-9-]{0,31}', name):
            raise ValueError('agent names must be domain-prefixed')
    if len({profile[k] for k in ('chief_agent', 'lead_agent', 'worker_agent')}) != 3:
        raise ValueError('profile agents must be distinct')
    if {profile[k] for k in ('chief_agent', 'lead_agent', 'worker_agent')} & {ident+'-shape', ident+'-checkpoint'}:
        raise ValueError('agent name collides with scoped workflow')
    for key in ('responsibility', 'remit', 'tone'):
        if not isinstance(profile[key], str) or not profile[key].strip() or any(x in profile[key] for x in ('{{', '\x00')):
            raise ValueError('invalid profile text')
    if profile['adapter'] != 'opencode-local-notes-a2a-v1':
        raise ValueError('unsupported host/tool adapter')
    return profile


def compose(profile, home, shared_home, runway_home, directory):
    ident = profile['id']
    # Reuse the independent lead schema/composer, not chief-owned workflows.
    from render import pack_values, owner_values
    values = {**pack_values(profile['lead_packs']),
              'APPROVED_PLAN_AUTHORITY': read('kits/shared/approved-plan-authority.md'),
              'OPERATIONAL_RECORD': '',
              **owner_values(dict(mode='agent', pointer=str(home / 'chief.json'), label=ident + ' chief')),
              'INTRO': 'You are the lead for one outcome. Own the plan, bounded jobs, decisions, verification and log.',
              'MODEL_POLICY': f'## Shared models and usage\n\nRead `{shared_home}/models.md` as the shared authority; do not copy or edit it. The shared Runway registry/ledger is `{runway_home}`. Use only available authorized tools or ask the technical owner for routing assistance. Paid use needs explicit outcome approval. Keep lead quality Strong; checkpoint before moving workers.',
              'WORKER_ROUTING': 'Use only the scoped worker agent and available authorized model; never bypass a missing route.',
              'LEAD_AGENT': profile['lead_agent'], 'CHIEF_AGENT': profile['chief_agent'],
              'CHECKPOINT_NAME': ident + '-checkpoint', 'SHAPE_NAME': ident + '-shape',
              'BRIEF_DIR': str(home), 'SESSION_ID_HELP': '`domain_identity`',
              'GOAL_INTRO': 'Own the whole outcome set by {{OWNER_NAME}} across turns until verified. Goal-mode activation is a host capability awaiting runtime proof here; do not claim it is enabled merely by creating a session.',
              'WORKER_SEND': 'existing transport through `domain_a2a_send` to its explicit local address with `expectReply: true` so the result returns automatically.',
              'SELF_ID': 'domain_identity', 'QUESTION_SEND': 'domain_a2a_send tool (to local/<your id>, expectReply true)',
              'RELAY_TOOL': '`domain_a2a_send`',
              'DELIVERY': 'To escalate, re-read the configured owner pointer and use `domain_a2a_send` to local/<session> with `expectReply: true`. Its final answer returns automatically. Never send a new acknowledgement. Write outcomes for the principal, with evidence last:',
              'SCOPE': '## Domain scope\n\n' + profile['remit'] + '\nCoordinate only this domain. Other chiefs own their domains. One lead owns each agreed outcome.',
              'TONE': '## Principal style\n\n' + profile['tone'] + '\nA detail block means written supporting detail, not a required voice format.',
              'RETURN_STYLE': '', 'ESCALATION_STYLE': 'two short sentences', 'QUESTION_STYLE': 'one short question',
              'MILESTONE_STYLE': 'two short sentences',
              'LEAD_START_POLICY': 'an available Strong-class model within the shared policy',
              'CHECKIN': '- **Checking in.** Read each outcome\'s `LEAD.md` and your open items. Use scoped agent messages only when the log is insufficient; do not inspect unrelated worker sessions.',
              'MODEL_MEMORY': f'- **Shared model policy:** `{shared_home}/models.md`, read-only here; never seed a separate copy.',
              'MODELS': f'## Models and usage\n\nThe shared installed policy is `{shared_home}/models.md`. The single Runway authority is `{runway_home}`. Do not create another ledger, account or daemon. Ask the technical owner for quota decisions when this narrow adapter has no routing tool. Never use paid models without explicit outcome permission.',
              'FLEET': '## Available tools\n\nUse this profile\'s native memory tools and local a2a. No shell, Code Mode or unrestricted session controller is available. If a tool is unavailable, report that limitation; do not improvise another channel.',
              'DEPTH_STYLE': '## Depth on demand\n\nWhen asked, show evidence, choices and uncertainty. Keep unsolicited updates about outcomes, not internal mechanics.',
              'EXAMPLES': '',
              'SHAPE_INTERACTION': 'Use the principal\'s configured style. Ask one outcome question at a time; keep detailed options and evidence in writing. Record decisions before replying.',
              'SHAPE_LOOKUP': 'Use only available authorized read/research tools and the shared policy reference. Do not run fleet tools or shell fallbacks from this narrow profile. Ask the responsible owner if a required capability is unavailable.',
              'INTRO_CHIEF': 'You are the principal\'s chief of staff for this domain. Own cross-outcome priorities, memory and escalations, not the leads\' internal decisions.'}
    chief = expand(read('kits/chief/core.md'), {**values, 'INTRO': values['INTRO_CHIEF']}).strip()
    shared = '\n\n'.join([LEVELS, read('kits/shared/docket.md'), read('kits/shared/fleet.md'),
                          expand(read('services/directory/instructions.md'), {'DIRECTORY_GUIDE': str(resource_paths(home)[-1]),
                                                                            'SERVICE_GUIDE': str(resource_paths(home)[0])}),
                          f'## Service references\n\nDirectory: `{directory}`. Voicestack accepts only the current technical chief. Request any approved reach-out through that owner over a2a; never impersonate it. Read `{resource_paths(home)[0]}` for ownership/limits.']).replace('`a2a_send`','`domain_a2a_send`')
    host = f'''\n\n## Scoped host contract\n\nUse `domain_identity` for your session id. Chief starts `{profile['lead_agent']}` via
`domain_lead_start` with directory, objective and model after an operator binds the
OpenChamber goal bridge. It can only start this configured lead, not arbitrary
actions/agents. Without that bridge, report blocked goal activation; do not claim
an active goal or silently substitute a transport-only session. For authorized
chief fresh-session and worker operations use `domain_a2a_create` and `domain_a2a_send`,
which capture and call the existing a2a transport with real caller context.
Leads create only `{profile['worker_agent']}` in their
own outcome folder; workers cannot delegate. Agent-owner questions use local
a2a messages with automatic replies. No inter-chief handoff uses session.send.
For fresh LEAD handover, checkpoint first, then use `domain_lead_start` with
`replacement: true`, the SAME outcome directory, explicit model, and the exact logged
goal plus instructions to read LEAD.md and continue. Only the currently recorded
goal lead can replace itself. The returned id belongs in the log and worker/owner
handover. Never use a2a creation for a required goal lead or its replacement.
For chief-only fresh handover use the same agent/directory with `nest: false`.
Preserve the configured checkpoint and live pointer. Goal mode is an OpenChamber host feature, not an a2a field: actual goal activation,
automatic wakeups and fresh-session transfer remain gated on later runtime proof.
Do not claim goal mode was enabled by domain_a2a_create. If it is required and unavailable,
report the blocked capability. Never broaden the tool catalog to work around it.
'''
    return chief + '\n\n' + shared + host, lead_prompt(values) + host, values


def managed_surfaces(profile, home):
    return [home / f'.opencode/agents/{profile[role+"_agent"]}.md' for role in ('chief','lead','worker')] + [
        home / f'.opencode/{kind}/{profile["id"]}-{name}' / 'SKILL.md' if kind == 'skills'
        else home / f'.opencode/commands/{profile["id"]}-{name}.md'
        for kind in ('commands','skills') for name in ('shape','checkpoint')
    ] + [home / '.opencode/plugins/chief-domain/index.ts', home / 'AGENTS.md',
         home / '.opencode/skills/upstream-courtesy/SKILL.md'] + resource_paths(home)


def permissions(home, role, checkpoint, shape, shared, directory, managed=()):
    # Native V2 documented actions; catalog filtering is separately required.
    rules = [{'action': '*', 'resource': '*', 'effect': 'deny'}]
    def allow(action, resource):
        rules.append(dict(action=action, resource=resource, effect='allow'))
    allow('external_directory', str(home) + '/*')
    allow('read', str(home) + '/*')
    allow('read', '*')  # Narrow external boundaries remain denied; internal reads are useful.
    allow('webfetch', '*')
    allow('websearch', '*')
    allow('domain_identity', '*')
    allow('domain_a2a_send', '*')
    if role != 'worker':
        allow('domain_a2a_create', '*')
    if role != 'worker':
        allow('domain_lead_start', '*')
    if role == 'chief':
        allow('edit', str(home) + '/*')
        for file in ('brief.md', 'open.md', 'principal.md', 'chief.json', 'ideas.md', 'handoffs.json', 'archive/*', '*.md'):
            allow('edit', file)
    elif role == 'lead':
        for file in ('LEAD.md', '*/LEAD.md', 'lead/*', '*/lead/*'):
            allow('edit', file)
    else:
        for file in ('output/*', 'notes/*', str(home) + '/outcomes/*/output/*', str(home) + '/outcomes/*/notes/*'):
            allow('edit', file)
    # Shared authority is readable only at named files, never editable.
    for parent, files in ((shared, ['models.md', 'chief.json']), (directory.parent, [directory.name])):
        allow('external_directory', str(parent) + '/*')
        rules.append(dict(action='read', resource=str(parent) + '/*', effect='deny'))
        for file in files:
            allow('read', str(parent / file))
    for prefix in ('.opencode/*', '.kit-*', 'AGENTS.md', str(home / 'AGENTS.md'), str(home) + '/.opencode/*', str(home) + '/.kit-*'):
        rules.append(dict(action='edit', resource=prefix, effect='deny'))
    for file in managed:
        for resource in (str(file), str(file.relative_to(home))):
            rules.append(dict(action='edit', resource=resource, effect='deny'))
    # Only fixed guide leaves are readable; sibling/private resources stay denied.
    for prefix in (str(home / '.kit-resources') + '/*', '.kit-resources/*'):
        rules.append(dict(action='read', resource=prefix, effect='deny'))
    for file in resource_paths(home):
        for resource in (str(file), str(file.relative_to(home))):
            allow('read', resource)
    allow('skill', checkpoint)
    allow('skill', 'upstream-courtesy')
    # Host-only credentials and durable no-replay state never enter model tools.
    binding = home.parent.parent / '.config/chief-of-staff/goal-bindings'
    for action in ('read', 'edit', 'external_directory'):
        rules.append(dict(action=action, resource=str(binding) + '/*', effect='deny'))
    if role == 'chief':
        allow('skill', shape)
    return rules
