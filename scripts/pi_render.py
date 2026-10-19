"""Explicit Pi preset composition; no runtime discovery or host contact."""
import json

from render import (read, expand, pack_values, owner_values, LEAD_HOST_DEFAULTS,
                    LEVELS)
from courtesy import skill

# Fixed Pi copy surface; independent of the scoped OpenCode resource installer.
GUIDES = ('README.md', 'models/README.md', 'runway/README.md', 'docket/README.md',
          'fleet/README.md', 'voicestack/README.md', 'directory/README.md')


def section(text, start, end, replacement):
    before, found, tail = text.partition(start)
    _, last, after = tail.partition(end)
    if not found or not last:
        raise ValueError('Pi composition seam missing')
    return before + replacement + '\n\n' + end + after


def compose(home, brief, capabilities):
    if (any(x not in ('pi-subagents', 'pi-goal-x') for x in capabilities)
            or len(set(capabilities)) != len(capabilities)):
        raise ValueError('Pi capabilities must be unique pi-subagents / pi-goal-x IDs')
    profile = json.loads(read('profiles/pi/profile.json'))
    if (set(profile) != {'version', 'lead_packs', 'chief_agent', 'lead_agent'}
            or type(profile['version']) is not int or profile['version'] != 1
            or profile['chief_agent'] != 'chief-of-staff' or profile['lead_agent'] != 'chief-lead'):
        raise ValueError('invalid fixed Pi profile')
    values = {**LEAD_HOST_DEFAULTS, **pack_values(profile['lead_packs']),
              **owner_values({'mode': 'principal', 'style': 'Short outcome summaries; evidence last.'}),
              'BRIEF_DIR': str(brief), 'LEAD_AGENT': 'chief-lead',
              'CHECKPOINT_NAME': 'chief-lead-checkpoint', 'SHAPE_NAME': 'chief-shape',
              'INTRO': 'You own one approved project outcome in the current Pi conversation.',
              'GOAL_INTRO': 'Work toward the whole approved outcome. Base Pi has no active goal mode.',
              'WORKER_WORK': '', 'WORKSPACE': '',
              'MODEL_POLICY': 'Use available authorized models. Paid use needs project approval.',
              'LOG_TEMPLATE': read('kits/lead/log.template.md')}
    workers = ('## Workers\n\nUse available read, bash, edit and write tools for permitted local work. '
               'This template grants no tools or permissions and creates no child session. '
               'Give workers complete briefs, one writer per shared file set, finite fanout and '
               'deadlines. Check their results. Checkpoint before changing a worker scope/model. '
               'Stop your own runaway jobs first; never use broad process kills.\n\n')
    if 'pi-subagents' in capabilities:
        workers += read('hosts/pi/subagents.md')
    else:
        workers += 'Delegation is not configured. Do permitted work locally or ask the operator for a handover.'
    goal = ('## Goal mode\n\nPreserve the full objective and verify every criterion. '
            'Record work, checks, remaining tasks and decisions in LEAD.md. '
            'Stop on principal constraints and repeated rejection. Waiting is not work; '
            'checkpoint and end the turn without polling or automatic-wakeup assumptions. '
            'A text message beginning Goal: records a proposed objective change; it activates no runtime.\n\n')
    if 'pi-goal-x' in capabilities:
        goal += read('hosts/pi/goal.md')
        values['GOAL_INTRO'] = 'Goal mode is optional and requires explicit operator activation as described below.'
    lead = read('kits/lead/core.md')
    lead = section(lead, 'At kickoff,', '\nMake the call,',
                   'At kickoff, save the initial plan in PROJECT.md with a # title and ## Steps checklist. '
                   'Show it to the principal and wait for approval before building. Tick steps as they land. '
                   'Only scope changes need renewed approval; operational plans remain yours.')
    lead = section(lead, '## Workers', '## Worktree hygiene', workers)
    lead = section(lead, '## Goal mode', '## Stop conditions', goal)
    # Pi has no native session/worktree registry. Preserve the clean-only Git rule;
    # inability to prove another session's location protects its worktree.
    lead = lead.replace('native worktree metadata and live session locations/status',
                        'available ownership records and live session locations/status')
    lead += ('\n\nInvoke /skill:chief-lead-checkpoint before handover. In a fresh Pi '
             'conversation load /chief-lead again. Run /reload after resource updates.')
    lead = expand(lead, values)
    lead = lead.replace('reconcile native worktree metadata and live session locations/status',
                        'reconcile available ownership records and live session locations/status')
    lead = lead.replace(LEVELS, LEVELS.split('\nA lead reports')[0])
    lead = lead.replace("These are the only files you\nwrite yourself.",
                        'Keep coordination records there. Implementation writes stay within the approved project scope.')
    lead = lead.replace("Don't claim work happened until a worker confirms it and you have checked.",
                        "Don't claim work happened until you have checked the actual result.")

    chief_values = {**values, **json.loads(read('profiles/technical/chief-style.json')),
                    'INTRO': 'Coordinate the principal\'s projects, priorities and durable brief in this Pi conversation.',
                    'TONE': 'Use short plain outcome summaries. Show detail when asked.',
                    'SCOPE': read('profiles/technical/scope.md'),
                    'DEPTH_STYLE': '## Depth on demand\n\nShow evidence and implementation detail when asked.',
                    'MODEL_MEMORY': '', 'MODELS': '', 'FLEET': '', 'EXAMPLES': '',
                    'SHAPE_INTERACTION': 'Ask the principal here; record the decision before proceeding.',
                    'SHAPE_LOOKUP': 'Use available authorized tools; delegate only with explicit configured capability.',
                    'SESSION_ID_HELP': 'operator-confirmed Pi conversation identity',
                    'CHECKPOINT_NAME': 'chief-checkpoint', 'SHAPE_NAME': 'skill:chief-shape'}
    leads = read('hosts/pi/leads.md')
    if 'pi-subagents' not in capabilities:
        leads = section(leads, 'When optional delegation', 'Without delegation,',
                        'Delegation is not configured in this preset.')
    chief = section(read('kits/chief/core.md'), '## Leads', '## Judgment', leads)
    chief = section(chief, '- **`chief.json`', '- **`archive/`',
                    '- Pi conversation identity and report routes are operator-maintained notes. '
                    'Do not write an OpenChamber session pointer or treat one as a delivery channel.')
    chief = section(chief, '**Checkpoint and fresh sessions.**', '{{MODELS}}',
                    'Use /skill:chief-checkpoint before handover. For a fresh Chief, ask the operator '
                    'to start Pi in the same brief folder and invoke /chief-of-staff to read the brief. '
                    'This template creates no successor session or automatic report route.')
    chief = expand(chief, chief_values)
    chief += '\n\n' + LEVELS.split('\nA lead reports')[0]
    chief = chief.replace('The startup note `AGENTS.md`, which is\nalways loaded in this folder, says the same.',
                          'Load /chief-of-staff in every fresh Pi conversation before acting.')
    if 'pi-subagents' in capabilities:
        chief += '\n\n' + read('hosts/pi/subagents.md')
    chief += '\n\nRun /reload after resource updates. Load /chief-of-staff in every fresh conversation.'
    shared = ('\n\n' + read('kits/shared/docket.md') + '\n\n' + read('kits/shared/fleet.md')
              + '\n\nThese shared-service rules require separately configured external tools. '
              'The Pi preset supplies no service connection, scheduling or automatic wakeup. '
              'If unavailable, record the limitation and ask the operator; never improvise a channel.')
    marker = '<!-- managed by chief-of-staff/install.sh; Pi preset -->'
    def prompt(description, body):
        return f'---\ndescription: {description}\nargument-hint: "[task]"\n---\n{marker}\n\n{body}{shared}\n\n$ARGUMENTS\n'
    def workflow(name, description, body):
        return f'---\nname: {name}\ndescription: {description}\n---\n{marker}\n\n{body}\n'
    base = home / '.pi/agent'
    checkpoint = section(read('kits/lead/skills/checkpoint.md'), 'For `fresh`,',
                         'Never require a',
                         'For `fresh`, checkpoint first, then ask the operator to start Pi in the same '
                         'project and load /chief-lead with LEAD.md and its next action. Record the '
                         'handover; no child/session id automatically transfers execution. ')
    shape = section(read('kits/chief/skills/shape/workflow.md'), 'At kickoff,', '## When to stop',
                    'At kickoff, record the initial plan in PROJECT.md with a # title and ## Steps '
                    'checklist. Show it to the principal and wait for approval before building. '
                    'Tick steps as they land. Record approved scope changes visibly. Operational '
                    'plans need no approval; changing deliverables does.')
    outputs = {
        base / 'prompts/chief-of-staff.md': prompt('Coordinate projects and principal decisions', chief),
        base / 'prompts/chief-lead.md': prompt('Own one approved engineering or research outcome', lead),
        base / 'skills/chief-lead-checkpoint/SKILL.md': workflow('chief-lead-checkpoint', 'Checkpoint the included Pi lead', expand(checkpoint, values)),
        base / 'skills/chief-checkpoint/SKILL.md': workflow('chief-checkpoint', 'Checkpoint Chief before handover',
            f'Read and reconcile {brief}/brief.md, open.md and principal.md. Record decisions, promises, '
            'pending questions, projects, workers and effects; archive old closed items. Verify a new '
            'conversation can resume from files. For fresh, ask the operator to start Pi in the brief '
            'folder and invoke /chief-of-staff. Never launch a successor or assume automatic lead delivery.'),
        base / 'skills/chief-shape/SKILL.md': workflow('chief-shape', 'Agree project scope and plan before implementation',
            expand(shape, {**chief_values,
                'TEMPLATE': read('kits/chief/skills/shape/PROJECT.template.md')})),
    }
    # Guide copies are ordinary managed resources, never extension entry points.
    for source in GUIDES:
        outputs[base / 'chief-resources/services' / source] = read('services/' + source) + '\n'
    outputs[base / 'prompts/chief-of-staff.md'] += '\nService guides: ' + str(base / 'chief-resources/services/README.md') + '\n'
    return outputs, base / 'skills/upstream-courtesy/SKILL.md', skill()
