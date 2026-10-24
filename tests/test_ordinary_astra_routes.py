"""Exercise the documented opt-in with synthetic operator inputs."""
import copy
import json
from pathlib import Path
import unittest
from tests.test_routing import NOW, fixture, model, route, source
from runway.policy import decide, validate

ROOT = Path(__file__).resolve().parents[1]


class OrdinaryAstraTests(unittest.TestCase):
    def test_documented_routes_and_admission(self):
        self.assertEqual(json.loads((ROOT / 'routing/routes.example.json').read_text())['routes'], [])
        base = dict(route('operator'), id='gpt-mid')
        config = {'version': 1, 'routes': [base]}
        code = (ROOT / 'routing/ORDINARY-ASTRA.md').read_text().split('```python\n')[1].split('```')[0]
        exec(code, {'config': config})
        validate(config)
        _, snapshot, catalog, task = fixture()
        snapshot['sources'] = [source('operator')]
        catalog['models'] = [dict(model('openai'), id='gpt-6-astra', variants=[{'id': 'high'}, {'id': 'medium'}])]
        for r, variant, categories in zip(config['routes'][1:], ('high', 'medium'),
                                          (['research', 'implement', 'hard'], ['research', 'implement'])):
            self.assertEqual(r, dict(base, id=r['id'], model='openai/gpt-6-astra', variant=variant, categories=categories))
            for category in ('research', 'implement', 'hard'):
                result = decide({'version': 1, 'routes': [r]}, snapshot, catalog,
                                dict(task, category=category), [], None, NOW)
                self.assertEqual(bool(result['selected']), category in categories)
            missing = copy.deepcopy(catalog)
            missing['models'][0]['variants'] = []
            self.assertFalse(decide({'version': 1, 'routes': [r]}, snapshot, missing, task, [], None, NOW)['selected'])
