"""Fixed, read-only guide copies; no executable service code or private state."""
from pathlib import Path


GUIDES = ('README.md', 'models/README.md', 'runway/README.md', 'docket/README.md',
          'fleet/README.md', 'voicestack/README.md', 'directory/README.md')


def resource_paths(home):
    return [Path(home) / '.kit-resources/services' / name for name in GUIDES]


def resource_outputs(home, marker):
    source = Path(__file__).resolve().parent.parent / 'services'
    return {p: marker + '\n\n' + (source / name).read_text().strip() + '\n'
            for p, name in zip(resource_paths(home), GUIDES)}
