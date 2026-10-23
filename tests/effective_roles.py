"""Public test fixture: explicit scenario composition, not a permission parser."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_policy import agent_parts, winner
from lean_roles import procedures
from render import render
from unittest.mock import patch


def effective(template, brief, names):
    """Load named scenario procedures only; never append old unreferenced prose."""
    text = render(template, brief)
    available = procedures(brief)
    for name in names:
        ident = 'reset-' + name
        if name != 'shape':
            assert ident in text, 'missing explicit procedure trigger: ' + ident
        else:
            assert 'INITIAL PROJECT PLAN' in render('workflows/shape/hosts/skill.md', brief)
        procedure = available[ident]
        assert 'opencode/autoinvoke: false' in procedure
        assert '{{' not in procedure
        text += '\n\n' + procedure
    return text


def rules(text):
    return agent_parts(text)[2]


def effect(text, action, resource):
    return winner(action, resource, rules(text))['effect']


def assert_current_exports(test, actual, source, home, brief):
    """Finite approved lean-role/procedure export delta, not a golden refresh.

    Independent target manifest + canonical bodies; unknown additions/removals or
    mutated leaves fail. Separate policy tests retain authority/license/ownership.
    No old repository, session export, environment or enrollment is imported.
    """
    targets = {
        '.config/opencode/agents/chief-of-staff.md':'hosts/opencode.md',
        '.config/opencode/agents/lead.md':'hosts/opencode-lead.md',
        '.config/opencode/plugins/chief-role-context.js':'services/role-context.mjs',
        '.config/opencode/commands/shape.md':'workflows/shape/hosts/opencode-command.md',
        '.config/opencode/commands/checkpoint.md':'workflows/checkpoint/hosts/opencode-command.md',
        '.claude/output-styles/chief-of-staff.md':'hosts/claude-output-style.md',
        '.claude/agents/chief-of-staff.md':'hosts/claude-agent.md',
        '.claude/agents/lead.md':'hosts/claude-lead-agent.md',
        '.claude/skills/shape/SKILL.md':'workflows/shape/hosts/skill.md',
        '.claude/skills/checkpoint/SKILL.md':'workflows/checkpoint/hosts/skill.md',
        '.codex/chief-of-staff.config.toml':'hosts/codex.config.toml',
        '.codex/lead.config.toml':'hosts/codex-lead.config.toml',
        '.codex/skills/shape/SKILL.md':'workflows/shape/hosts/skill.md',
        '.codex/skills/shape/agents/openai.yaml':'workflows/shape/hosts/codex-openai.yaml',
        '.codex/skills/checkpoint/SKILL.md':'workflows/checkpoint/hosts/skill.md',
        '.codex/skills/checkpoint/agents/openai.yaml':'workflows/checkpoint/hosts/codex-openai.yaml',
    }
    for root in ('.config/opencode', '.claude', '.codex'):
        targets[root+'/skills/upstream-courtesy/SKILL.md']='skills/upstream-courtesy/SKILL.md'
        for name in ('delivery-outlook','comparative-review'):
            targets[root+'/skills/'+name+'/SKILL.md']='kits/shared/skills/'+name+'.md'
    names=('worker-dispatch','worktree-safety','dispatch-events','checkpoint','reporting','delivery-outlook','comparative-review','shape','upstream-courtesy')
    for name in names:
        targets['.config/opencode/skills/reset-'+name+'/SKILL.md']='reset-procedure:reset-'+name
        targets['.local/share/chief-of-staff/reset/reset-'+name+'.md']='reset-procedure:reset-'+name
    for name in ('chief-openchamber','chief-portfolio','nod-alert','chief-nod','chief-images-server'):
        targets['.local/bin/'+name]='scripts/'+name
    targets['.local/share/chief-of-staff/home-infra.md']='services/home/reference.md'
    normalized=lambda text:text.replace(str(Path(source).resolve()),'<SOURCE>').replace(str(ROOT.resolve()),'<SOURCE>').replace(str(home),'<HOME>')
    with patch.object(Path, 'home', return_value=Path(home)):
        expected={'<HOME>/'+target:normalized(render(template,str(brief))+'\n') for target,template in targets.items()}
        for name in ('AGENTS.md','CLAUDE.md'):
            key=normalized(str(Path(brief)/name))
            expected[key]=normalized(render('kits/chief/memory/'+name,str(brief))+'\n')
        # Existing public-only fixed guide copies are part of the finite manifest,
        # not an unbounded snapshot or executable integration surface.
        from service_resources import resource_outputs
        for path,text in resource_outputs(brief,'<!-- managed by chief-of-staff service guides -->').items():
            expected[normalized(str(path))]=normalized(text+'\n')
    test.assertEqual(set(actual),set(expected),'Only the explicitly approved export target delta is allowed')
    for name in expected:
        test.assertEqual(actual[name],expected[name],name)
