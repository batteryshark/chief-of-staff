"""Remove only three exact, independently validated NEW skill leaves, never prose."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from courtesy import skill


def approved_n1(text):
    """Exact finite approved changes in NEW courtesy leaves only; not normalization."""
    changes = (
        ('  guidance and AI-use policy. Search relevant docs and open AND closed issues/PRs\n'
         '  for duplicates. Unknown/unavailable policy stays unknown: defer posting.\n',
         '  guidance and AI-use policy; search docs and open AND closed issues/PRs for duplicates.\n'
         '  Unknown/unavailable policy stays unknown: defer posting. Confirmed\n'
         '  absence of a published AI policy is not refusal; follow known contribution rules.\n'),
        ('  evade that refusal. Concise human-readable prose is not hiding AI use or\n',
         '  evade that refusal, even with principal approval. Concise prose is not hiding AI use or\n'),
        ('  exact destination, content, current revision and channel. Earlier permission,\n'
         '  project policy or a worthy bug does not authorize changed content, another bug\n'
         '  or later contact. Local skill creation/installation is not reporting permission.\n',
         '  exact actions, destinations, content, revisions and channels; a finite enumerated\n'
         '  set may be approved in advance. Changed/unlisted actions need a fresh yes, never\n'
         '  assumed follow-up. Local skill creation/installation is not reporting permission.\n'),
        ('  fresh approval. Respect maintainer decisions; no repeated pings, duplicate\n',
         '  exact advance approval or a fresh yes. Respect decisions; no repeated pings, duplicate\n'),
        ('## Private handoff (not an upstream form)\n\n', '## Private handoff (not an upstream form)\n'),
    )
    for old, new in changes:
        assert text.count(old) == 1
        text = text.replace(old, new, 1)
    return text


def existing_outputs(outputs):
    result = dict(outputs)
    for prefix in ('.config/opencode', '.claude', '.codex'):
        path = '<HOME>/' + prefix + '/skills/upstream-courtesy/SKILL.md'
        assert result.pop(path) == skill() + '\n', path
    assert len(result) == 19
    return result
