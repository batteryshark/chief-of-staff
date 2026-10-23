#!/usr/bin/env python3
"""Package explicit always-loaded reset prose, without installing or registering it.

Manifest: {"chief": [absolute source paths], "lead": [absolute source paths]}.
Each list must include ALL kit prose loaded for that role, including host/startup
fragments and catalog descriptions if used. On-demand documents are not included.
No legacy host body is appended. Permission metadata comes from the kit host.
"""
import argparse
import json
from pathlib import Path
import re

from install_paths import DestinationRoot

ROOT = Path(__file__).resolve().parents[1]
CAPS = {'chief': (150, 1600), 'lead': (100, 1200)}


def package(manifest, brief):
    if not isinstance(manifest, dict) or set(manifest) != set(CAPS):
        raise ValueError('declare all always-loaded sources for chief and lead')
    if not Path(brief).is_absolute() or str(Path(brief).resolve()) != brief:
        raise ValueError('canonical absolute brief required')
    result = {}
    for role, (line_cap, word_cap) in CAPS.items():
        sources = manifest[role]
        if (not isinstance(sources, list) or not sources
                or any(not isinstance(p, str) or not Path(p).is_absolute() for p in sources)
                or len(set(sources)) != len(sources)):
            raise ValueError('nonempty unique absolute source list required')
        parts = [Path(p).read_text().strip() for p in sources]
        if any(not p or p.startswith('---') for p in parts):
            raise ValueError('sources must be prose, not frontmatter or permission metadata')
        body = '\n\n'.join(parts) + '\n'
        lines, words = len(body.splitlines()), len(body.split())
        if (lines > line_cap or words > word_cap or '\t' in body
                or any(len(line) > 110 for line in body.splitlines())):
            raise ValueError(f'{role} exceeds prose budget: {lines} lines, {words} words')
        template = 'opencode.md' if role == 'chief' else 'opencode-lead.md'
        header = (ROOT / 'hosts' / template).read_text()[4:].split('\n---\n', 1)[0]
        # Empty description adds no uncounted prose. All other fields here are
        # tool-enforced metadata, never an extra instruction-body allowance.
        header = re.sub(r'^description:.*$', 'description: ""', header, flags=re.M)
        header = header.replace('{{BRIEF_DIR}}', brief)
        header = header.replace('{{RUNWAY_WORKFLOW}}', str(ROOT / 'routing/WORKFLOW.md'))
        header = header.replace('{{HOME_INFRA}}',
                                str(Path.home() / '.local/share/chief-of-staff/home-infra.md'))
        # The public host header also protects fixed installed documentation.
        # Resolve only this explicit metadata slot; never append legacy prose.
        from service_resources import resource_paths
        rules = [(action, prefix, 'deny')
                 for prefix in (brief + '/.kit-resources/*', '.kit-resources/*')
                 for action in ('read', 'edit')]
        rules += [('read', resource, 'allow') for guide in resource_paths(brief)
                  for resource in (str(guide), str(guide.relative_to(brief)))]
        header = header.replace('{{RESOURCE_PERMISSIONS}}', '\n'.join(
            f'  - action: {action}\n    resource: {json.dumps(resource)}\n    effect: {effect}'
            for action, resource, effect in rules))
        if '{{' in header:
            raise ValueError('unresolved permission placeholder')
        for action in ('shell', 'subagent', 'execute', 'openchamber*', 'a2a*', 'runway'):
            header += f'\n  - action: {action}\n    resource: "*"\n    effect: deny'
        header += '\nsteps: 10'
        result[role] = '---\n' + header + '\n---\n' + body
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--brief', required=True)
    parser.add_argument('--output', type=Path, help='absent-only review files; never an agents directory')
    args = parser.parse_args()
    rendered = package(json.loads(args.manifest.read_text()), args.brief)
    if args.output:
        output = args.output.resolve()
        if 'agents' in output.parts or '.opencode' in output.parts:
            raise ValueError('review packaging only; not an agent installation')
        targets = [output / f'{role}-reset-candidate.md' for role in rendered]
        DestinationRoot(output).validate_all(targets)
        if any(p.exists() or p.is_symlink() for p in targets):
            raise ValueError('retained package collision; never overwrite')
        output.mkdir(parents=True, exist_ok=True)
        for role, target in zip(rendered, targets):
            with target.open('x') as f:
                f.write(rendered[role])
    for role, text in rendered.items():
        body = text.split('\n---\n', 1)[1]
        print(f'{role}: {len(body.splitlines())} prose lines, {len(body.split())} words')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, TypeError) as e:
        raise SystemExit(str(e))
