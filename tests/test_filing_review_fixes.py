"""Adversarial pure-policy tests; fictional observations only."""
import copy
import hashlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kits/chief/desk/filing'))
import questions_policy as qp


class PolicyReviewTests(unittest.TestCase):
    def setUp(self):
        self.r = {'report_id': 'fictional-current', 'project': '/fictional/research', 'lead_session': 'fictional-lead',
                  'questions': ['May I proceed?'], 'landed': '', 'next': '', 'your_part': None}
        self.text = 'No open questions.'
        self.receipts = {}

    def review(self, classification='unknown', evidence=None):
        args = (self.r, self.receipts, 'fictional-open', 'fictional-open', self.text,
                hashlib.sha256(self.text.encode()).hexdigest(), classification)
        return qp.review(*args, evidence=evidence) if evidence is not None else qp.review(*args)

    def receipt(self, **scope):
        return {'report': {**self.r, 'report_id': 'fictional-prior', **scope}, 'completed': [
            {'action': {'type': 'forward'}, 'result': {'dispatched': True}}]}

    def evidence(self, question=None):
        return {'question': question or self.r['questions'][0], 'project': self.r['project'],
                'lead_session': self.r['lead_session'], 'basis': 'current_chief_open',
                'excerpt': self.text, 'source_sha256': hashlib.sha256(self.text.encode()).hexdigest()}

    def test_unrelated_priorask_status_never_suppresses(self):
        for field in ('landed', 'next', 'your_part'):
            for phrase in ('Already asked supplier', 'Previously asked', 'Asked through chief', 'Asked the chief', 'Already with the chief'):
                self.r[field] = phrase
                self.assertEqual(self.review('new_unasked')['state'], 'eligible')
                self.assertEqual(self.review()['state'], 'pending')

    def test_cross_project_and_other_lead_not_receipts(self):
        for scope in ({'project': '/fictional/other-study'}, {'lead_session': 'other-lead'}, {'project': None}, {'lead_session': None}):
            self.receipts = {'old': self.receipt(**scope)}
            self.assertEqual(self.review()['state'], 'pending')
            self.assertEqual(self.review('new_unasked')['state'], 'eligible')

    def test_ambiguous_open_phrase_is_only_candidate(self):
        self.text = 'Someone said: May I proceed?'
        for classification in ('unknown', 'new_unasked', 'already_open'):
            self.assertEqual(self.review(classification)['state'], 'pending')

    def test_actual_completed_same_scope_exact_coverage(self):
        self.receipts = {'old': self.receipt(questions=[' MAY I  proceed? '])}
        self.assertEqual(self.review()['state'], 'deduplicated')
        self.r['questions'].append('New question?')
        self.assertEqual(self.review('new_unasked')['state'], 'pending')

    def test_heuristic_suppressed_receipt_not_proof(self):
        self.receipts = {'old': {'report': {**self.r, 'report_id': 'fictional-prior'}, 'suppressed_actions': [
            {'reason': 'question already in own receipt or chief-open'}]}}
        self.assertEqual(self.review()['state'], 'pending')
        self.assertEqual(self.review('new_unasked')['state'], 'pending')
        self.text = '/fictional/research | fictional-lead | Start permission open.'
        self.receipts['old']['question_review'] = {
            'source': 'fictional-open', 'source_sha256': hashlib.sha256(self.text.encode()).hexdigest(),
            'evidence': [self.evidence()]}
        self.assertEqual(self.review()['state'], 'deduplicated')

    def test_reworded_requires_precise_current_scoped_evidence(self):
        self.text = '/fictional/research | fictional-lead | Permission to start the experiment is open.'
        self.assertEqual(self.review('already_open')['state'], 'pending')
        evidence = self.evidence()
        self.assertEqual(self.review('already_open', [evidence])['state'], 'deduplicated')
        for key, value in (('question', 'Other?'), ('project', '/wrong'), ('lead_session', 'wrong'),
                           ('excerpt', 'absent'), ('source_sha256', '0'*64), ('basis', '')):
            self.assertEqual(self.review('already_open', [{**evidence, key: value}])['state'], 'pending')
        self.text = 'Ambiguous unscoped wording'
        self.assertEqual(self.review('already_open', [self.evidence()])['state'], 'pending')
        self.text = '/fictional/research-other | fictional-lead-other | Start is open.'
        self.assertEqual(self.review('already_open', [self.evidence()])['state'], 'pending')

    def test_all_questions_evidence_and_partial_mixed_pending(self):
        self.r['questions'].append('Which date?')
        self.text = '/fictional/research | fictional-lead | Start permission and date remain open.'
        first = self.evidence()
        self.assertEqual(self.review('already_open', [first])['state'], 'pending')
        all_evidence = [first, self.evidence('Which date?')]
        self.assertEqual(self.review('already_open', all_evidence)['state'], 'deduplicated')
        self.receipts = {'old': {'report': copy.deepcopy(self.r), 'question_review': {
            'source': 'fictional-open', 'source_sha256': hashlib.sha256(self.text.encode()).hexdigest(),
            'evidence': all_evidence}}}
        self.assertEqual(self.review()['state'], 'deduplicated')
        self.text += ' changed'
        self.assertEqual(self.review()['state'], 'pending')

    def test_empty_and_your_part_zero_forward(self):
        self.r.update(questions=[], your_part='May I proceed?')
        self.assertEqual(self.review()['state'], 'deduplicated')


if __name__ == '__main__':
    unittest.main()
