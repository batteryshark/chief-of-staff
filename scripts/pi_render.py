"""Explicit Pi preset composition; no runtime discovery or host contact."""
import json

from render import (read, expand, pack_values, owner_values, LEAD_HOST_DEFAULTS,
                    LEVELS, STRATEGIC_SKILLS, strategic_skill)
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


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Pi composition replacement seam missing or ambiguous')
    return text.replace(old, new, 1)


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
              'APPROVED_PLAN_AUTHORITY': read('kits/shared/approved-plan-authority.md'),
              'OPERATIONAL_RECORD': '', 'AGENT_REPORTING': '',
              **owner_values({'mode': 'principal', 'style': 'Short outcome summaries; evidence last.'}),
              'BRIEF_DIR': str(brief), 'LEAD_AGENT': 'chief-lead',
              'CHECKPOINT_NAME': 'chief-lead-checkpoint', 'SHAPE_NAME': 'chief-shape',
              'INTRO': 'You own one approved project outcome in the current Pi conversation. '
                       'The declared chief inbox is `{{BRIEF_DIR}}/inbox/`; use authorized plain '
                       'files only. This grants no session transport or new permissions.',
              'GOAL_INTRO': 'Work toward the whole approved outcome. Base Pi has no active goal mode.',
              'WORKER_WORK': '', 'WORKSPACE': '',
              'MODEL_POLICY': 'Use available authorized models. Paid use needs project approval.',
              'LOG_TEMPLATE': read('kits/lead/log.template.md')}
    workers = ('## Workers\n\nUse available read, bash, edit and write tools for permitted local work. '
               'This template grants no tools or permissions and creates no child session. '
               'Give workers complete briefs, one writer per shared file set, finite fanout and '
               'deadlines. Check their results. Checkpoint before changing a worker scope/model. '
               'Stop your own runaway jobs first; never use broad process kills. '
               'Small device glue, scripts and wiring go to a mid model with a tight brief; '
               'Strong/high is for genuinely hard design or reverse engineering.\n\n')
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
                    'Show it to the principal and wait for approval before building unless initial approval '
                    'is already recorded; do not reopen that decision. Tick steps as they land. '
                   'Only scope changes need renewed approval; operational plans remain yours.')
    lead = section(lead, '## Workers', '## Chief inbox', workers)
    # Canonical hosts keep their lead-owned native Note policy unchanged. Pi has
    # no native Knowledge adapter: retain its status shape locally, without a route.
    lead = section(lead, '## Project status — your Note', '## Workers',
                   '## Project status — local fallback\n\n'
                   'Keep one short current status in LEAD.md: Landed / Next / Your part / Updated '
                   '(ISO date/time with timezone). Update at milestones or changed principal needs, '
                   'not every turn. Keep the approved initial coarse plan ticked in PROJECT.md. '
                   'Operational plans need no extra approval. Pi supplies no native Knowledge Notes, '
                   'Plans or Todos; record that limitation rather than inventing tools. '
                   'Report decisions, approvals, principal hands, continue-or-shelve, serious shared '
                   'risk and results worth showing directly to the principal. Never route status through a desk.')
    lead = section(lead, '## Goal mode', '## Stop conditions', goal)
    # Pi has no native session/worktree registry. Preserve the clean-only Git rule;
    # inability to prove another session's location protects its worktree.
    lead = lead.replace('native worktree metadata and live session locations/status',
                        'available ownership records and live session locations/status')
    lead = lead.replace('native\nworktree/session ownership and state',
                        'available\nworktree/session ownership and state')
    lead += ('\n\nInvoke /skill:chief-lead-checkpoint before handover. In a fresh Pi '
             'conversation load /chief-lead again. Run /reload after resource updates.')
    lead = expand(lead, values)
    lead = lead.replace('reconcile native worktree metadata and live session locations/status',
                        'reconcile available ownership records and live session locations/status')
    lead = lead.replace(LEVELS, LEVELS.split('\nA lead reports')[0])
    lead = replace_once(lead, 'These and the one authorized\nchief inbox coordination record described above are the only files you write yourself.',
                        'Keep coordination records there or in the authorized chief inbox. Implementation writes stay within the approved project scope.')
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
    chief = section(chief, 'Leads own one short', "Protect the principal's attention:",
                    'Pi leads keep local Landed / Next / Your part / Updated status in LEAD.md. '
                    'Read that log for catch-ups; Pi supplies no native Knowledge or chief-portfolio '
                    'integration. Operational work stays lead-owned. No routine status pings or desk routes.')
    chief = section(chief, 'Actual principal decisions and current owner results', '- **Write first',
                    'Actual principal decisions and current owner results outrank stale summaries. '
                    'Pi uses the authorized files as its operational record; no native Knowledge adapter.\n\n')
    chief = section(chief, '- **`chief.json`', '- **`archive/`',
                    '- Pi conversation identity and report routes are operator-maintained notes. '
                    'Do not write an OpenChamber session pointer or treat one as a delivery channel.')
    chief = section(chief, '## Chief dashboard — your own Project Knowledge',
                    '**Checkpoint and fresh sessions.**',
                    '## Chief dashboard — file fallback\n\n'
                    'Pi supplies no native Knowledge adapter or automatic Notes/Todos writes. '
                    'In the SAME TURN as brief.md/open.md updates (and ideas.md when relevant), '
                    'before the final reply keep these files current as the full record. '
                    'Track every principal ask and Q/P id in open.md; record answers and ownership '
                    'transfers without losing unresolved asks. At checkpoint reconcile brief/open/ideas '
                    'and explicitly record native dashboard sync unavailable/out of sync in files '
                    'and reply. Do not invent APIs, read native backing stores or write another project.')
    chief += ('\n\nIn the existing file fallback, keep a short prioritized Suggested next action: '
              'project, exact action/decision, recommendation/default and relevant consequence. '
              'Separate READY principal actions, DEFERRED options and AGENT-OWNED outcomes. '
              'Ambiguous legacy records need agent-owned clarification, not a principal chore. '
              'Keep Q/P ids private; no principal Todo for a delegated promise.')
    chief = section(chief, '**Checkpoint and fresh sessions.**', '{{MODELS}}',
                    'Use /skill:chief-checkpoint before handover. For a fresh Chief, ask the operator '
                    'to start Pi in the same brief folder and invoke /chief-of-staff to read the brief. '
                    'This template creates no successor session or automatic report route.')
    chief = expand(chief, chief_values)
    chief += '\n\n' + LEVELS.split('\nA lead reports')[0]
    chief = replace_once(chief, 'The startup note `AGENTS.md`, which is\n  always loaded in this folder, says the same.',
                         'Load /chief-of-staff manually in every fresh Pi conversation before acting; '
                         'this preset installs no always-loaded startup file.')
    if 'pi-subagents' in capabilities:
        chief += '\n\n' + read('hosts/pi/subagents.md')
    chief += '\n\nRun /reload after resource updates. Load /chief-of-staff in every fresh conversation.'
    chief += '\n\nOn demand: /skill:delivery-outlook for forecasts; /skill:comparative-review for consequential ambiguous strategy/design.'
    shared = ('\n\n' + read('kits/shared/docket.md') + '\n\n' + read('kits/shared/fleet.md')
              + '\n\nThese shared-service rules require separately configured external tools. '
              'The Pi preset supplies no service connection, scheduling or automatic wakeup. '
              'If unavailable, record the limitation and ask the operator; never improvise a channel.')
    marker = '<!-- managed by chief-of-staff/install.sh; Pi preset -->'
    base = home / '.pi/agent'
    chief += '\n\nService guides: ' + str(base / 'chief-resources/services/README.md')
    def prompt(description, body):
        return f'---\ndescription: {description}\nargument-hint: "[task]"\n---\n{marker}\n\n{body}{shared}\n\n$ARGUMENTS\n'
    def workflow(name, description, body):
        return f'---\nname: {name}\ndescription: {description}\n---\n{marker}\n\n{body}\n'
    checkpoint = section(read('kits/lead/skills/checkpoint.md'), 'For `fresh`,',
                         'Never require a',
                         'For `fresh`, checkpoint first, then ask the operator to start Pi in the same '
                         'project and load /chief-lead with LEAD.md and its next action. Record the '
                         'handover; no child/session id automatically transfers execution. ')
    shape = section(read('kits/chief/skills/shape/workflow.md'), 'At kickoff,', '## When to stop',
                    'At kickoff, record the initial plan in PROJECT.md with a # title and ## Steps '
                     'checklist. Show it to the principal and wait for approval before building unless initial '
                     'approval is already recorded; do not reopen that decision. '
                    'Tick steps as they land. Record approved scope changes visibly. Operational '
                    'plans need no approval; changing deliverables does.')
    outputs = {
        base / 'prompts/chief-of-staff.md': prompt('Coordinate projects and principal decisions', chief),
        base / 'prompts/chief-lead.md': prompt('Own one approved engineering or research outcome', lead),
        base / 'skills/chief-lead-checkpoint/SKILL.md': workflow('chief-lead-checkpoint', 'Checkpoint the included Pi lead', expand(checkpoint, values)),
        base / 'skills/chief-checkpoint/SKILL.md': workflow('chief-checkpoint', 'Checkpoint Chief before handover',
            f'Read and reconcile {brief}/brief.md, open.md, ideas.md and principal.md. Record decisions, promises, '
            'pending questions, projects, workers and effects; archive old closed items. At EVERY '
            'catch-up and checkpoint read immediate inbox/*.md entries fully, consider action/brief/open '
            'items, and plain-move only processed entries to archive/inbox/ without overwrite or content '
            'changes. Unprocessed/unreadable entries stay unread; no automatic outward messages. '
            'Use plain files only; no native Knowledge adapter or invented session transport. '
            'Record native dashboard sync unavailable/out of sync in files and reply. '
            'This sweep does not replace SAME TURN file maintenance before the final reply. Verify a new '
            'conversation can resume from files. For fresh, ask the operator to start Pi in the brief '
            'folder and invoke /chief-of-staff. Never launch a successor or assume automatic lead delivery.'),
        base / 'skills/chief-shape/SKILL.md': workflow('chief-shape', 'Agree project scope and plan before implementation',
            expand(shape, {**chief_values,
                'TEMPLATE': read('kits/chief/skills/shape/PROJECT.template.md')})),
    }
    for name in STRATEGIC_SKILLS:
        outputs[base / f'skills/{name}/SKILL.md'] = strategic_skill(name)
    # Guide copies are ordinary managed resources, never extension entry points.
    for source in GUIDES:
        outputs[base / 'chief-resources/services' / source] = read('services/' + source) + '\n'
    return outputs, base / 'skills/upstream-courtesy/SKILL.md', skill()
