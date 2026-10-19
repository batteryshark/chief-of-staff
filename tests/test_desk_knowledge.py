"""Knowledge projection state only: never call native Knowledge/Canvas APIs."""
import test_desk as fixtures
import desk_store as desk
import unittest


class KnowledgeProjectionTests(unittest.TestCase):
    setUp = fixtures.DeskTests.setUp
    receive = fixtures.DeskTests.receive

    def test_one_note_intent_per_project_not_blind_duplicate_create(self):
        self.receive()
        first = self.store.knowledge_prepare('fixture')
        self.assertEqual(first['operation'], 'create-note')
        self.assertFalse(first['send'])
        second = self.store.knowledge_prepare('fixture')
        self.assertEqual(first['intent'], second['intent'])
        self.assertFalse(second['send'])

    def test_uncertain_create_reconciles_id_instead_of_recreate(self):
        self.receive()
        intent = self.store.knowledge_prepare('fixture')
        self.store.knowledge_result('fixture', intent['intent'], 'uncertain')
        self.assertEqual(self.store.knowledge_prepare('fixture')['state'], 'uncertain')
        self.store.knowledge_result('fixture', intent['intent'], 'applied', 'fixture-note-id', intent['proposed'])
        self.assertFalse(self.store.knowledge_prepare('fixture')['send'])
        self.assertEqual(self.store.knowledge_state('fixture')['note_id'], 'fixture-note-id')

    def test_late_success_keeps_id_and_next_update_uses_expected_body(self):
        self.receive()
        first = self.store.knowledge_prepare('fixture')
        self.receive({**self.report, 'id': 'new', 'source_revision': 2, 'landed': 'New milestone'},
                     {**self.context, 'message_id': 'newmsg'})
        result = self.store.knowledge_result('fixture', first['intent'], 'applied', 'owned-note', first['proposed'])
        self.assertTrue(result['pending_latest'])
        second = self.store.knowledge_prepare('fixture')
        self.assertEqual(second['operation'], 'update-note')
        self.assertEqual(second['expected'], first['proposed'])
        self.assertEqual(second['note_id'], 'owned-note')
        self.assertIn('New milestone', second['proposed'])

    def test_conflict_or_wrong_body_never_claims_fresh(self):
        self.receive()
        first = self.store.knowledge_prepare('fixture')
        with self.assertRaises(ValueError):
            self.store.knowledge_result('fixture', first['intent'], 'applied', 'other-note', 'unrelated content')
        self.store.knowledge_result('fixture', first['intent'], 'conflict')
        self.assertFalse(self.store.knowledge_prepare('fixture')['send'])
        self.assertTrue(self.store.receipt(1)['knowledge_pending'])

    def test_lead_claim_creates_no_principal_todo_and_plan_is_nudge_only(self):
        self.receive({**self.report, 'your_part': 'Principal approved; ask them to log in'})
        intent = self.store.knowledge_prepare('fixture')
        self.assertIsNone(intent['todo_intent'])
        self.assertIn('never infer ticked steps', intent['plan'])
        self.assertIn('With chief', intent['proposed'])

    def test_chief_attributed_wait_stages_owned_todo_and_inert_status(self):
        self.receive({**self.report, 'landed': '![image](https://invalid.example/image)\n# forged'})
        self.store.decision_update('fixture', 1, 'Try layout', 'chief Q-fixture asked')
        intent = self.store.knowledge_prepare('fixture')
        self.assertEqual(intent['todo_intent']['owner_marker'], 'chief-desk-wait:fixture')
        self.assertEqual(intent['todo_intent']['reference'], 'chief Q-fixture asked')
        self.assertNotIn('![image]', intent['proposed'])
        self.assertIn('observed 2026-10-01', intent['proposed'])
        self.assertEqual(intent['proposed'].splitlines()[0], 'fixture — project status')
        self.assertIn('chief-desk-status:fixture', intent['proposed'])
