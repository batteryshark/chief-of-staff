"""Final cap arithmetic and durable hold regression; no rollout pins."""
import json
from pathlib import Path
import unittest
import test_api_promo_native as fixture
from runway import promo


class FableBudgetTests(unittest.TestCase):
    setUp = fixture.NativeTests.setUp
    tearDown = fixture.NativeTests.tearDown

    def test_final_bound_and_existing_hold(self):
        self.assertEqual(4 * (128000 * 20 + 32768 * 50), 16793600)
        self.assertLessEqual(16793600, promo.RESERVES['api-fable'])
        self.assertEqual(promo.RESERVES['api-fable'], 17000000)
        self.credit.reserve('old-hold', 12000000, fixture.NOW)
        before = self.credit.db.execute('SELECT * FROM holds').fetchall()
        self.assertEqual(promo.plan({'route': 'api-fable', 'purpose': 'independent-review', 'text': 'fixture'})['reserve_micro_usd'], 17000000)
        self.assertEqual(self.credit.db.execute('SELECT * FROM holds').fetchall(), before)
        example = json.loads((Path(__file__).resolve().parents[1] / 'routing/api-promo.opencode.json').read_text())
        model = example['providers']['anthropic-promo']['models']['claude-fable-5-1']
        self.assertEqual(model['body']['max_tokens'], 32768)
        self.assertEqual(model['variants'][0]['id'], 'high')
