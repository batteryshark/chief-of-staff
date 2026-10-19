"""Fictional offline fixtures, NOT Luna runs or semantic safety proof."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import ast
import json
from pathlib import Path
import unittest

import desk_rules as d


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def fixture(relay=False, report_id='fiction-1', observed='2026-10-18T11:59:59Z'):
    scope = d.Scope('fiction-parser', '/fiction/parser', 'lead-fiction', 'lead-fiction',
                    'chief-fiction', 3, 'offline-parser', 'source-only-v2', 'enum-validation-v1')
    source = d.Source('fiction-decision-ledger', 'a' * 64, 7)
    record = d.Record('authority-1', 2, scope.chief, scope, source,
                      '2026-10-18T00:00:00Z', '2026-10-19T00:00:00Z', 0)
    delegation = replace(record, id='delegation-1', revision=4)
    decision = d.Decision(replace(record, id='decision-1'), 'parser-item',
        'Use the local enum parser for fictional source-only validation; nothing else.',
        d.text_hash('Use the local enum parser for fictional source-only validation; nothing else.'),
        'pure_technical') if relay else None
    family = 'recorded_technical_relay' if relay else 'technical_choice'
    choices = ('copy_recorded_decision',) if relay else ('local_enum_parser', 'local_table_parser')
    rule = d.Rule('relay-v1' if relay else 'parser-v1', 1, record, delegation,
        d.Approval('operator-fiction-approval', 'Strong-fiction-review-v1', d.CODE_VERSION,
                   'relay-v1' if relay else 'parser-v1', 1), family, choices, 1,
        d.RELAY_TEMPLATE if relay else d.TECH_TEMPLATE, decision)
    request = d.Request(family, choices, 'decision-1' if relay else None, 2 if relay else 0, ())
    report = d.Report(report_id, observed, scope, 'Choose a local validation strategy.', request)
    inp = d.HostInput('receipt-' + report_id, report_id, d.digest(report),
        '2026-10-18T12:00:00Z', scope.lead, scope.project_path, scope.epoch, 8)
    host = d.HostState(scope, source, inp, '2026-10-18T12:00:00Z',
        (d.RulePin(rule.id, 1, 2, delegation.id, 4),), (rule,),
        'decision-1' if relay else None, 2 if relay else 0, 'parser-item' if relay else None)
    proposal = d.Proposal(rule.id, choices[0], False, ())
    return host, report, proposal


def rebind(host, report):
    return replace(host, input=replace(host.input, report_id=report.id,
                                     report_sha256=d.digest(report)))


class BoundedRulesTests(unittest.TestCase):
    def run_case(self, host, report, proposal, disposition='escalate', now=NOW):
        result = d._evaluate_at(host, report, proposal, now)
        self.assertEqual(result.disposition, disposition, result.reasons)
        self.assertEqual(result.outward_effects, 0)
        if disposition == 'escalate':
            self.assertIsNone(result.intent)
            self.assertEqual(result.answer, '')
            self.assertTrue(result.reasons)
        self.assertTrue(json.loads(result.evidence_json)['engine'])
        return result

    def test_reusable_two_reports_and_deterministic_audits(self):
        h, r, p = fixture()
        a = self.run_case(h, r, p, 'routine_intent')
        self.assertEqual(a, self.run_case(h, r, p, 'routine_intent'))
        h2, r2, p2 = fixture(report_id='fiction-2', observed='2026-10-18T11:59:58Z')
        b = self.run_case(h2, r2, p2, 'routine_intent')
        self.assertEqual(a.answer, b.answer)
        self.assertNotEqual(a.evidence_json, b.evidence_json)
        self.assertEqual(h.rules, h2.rules)  # no report hash whitelist in rule
        self.assertEqual(a.intent.action_limit, 1)

    def test_second_choice_fixed_bounded_answer(self):
        h, r, p = fixture()
        result = self.run_case(h, r, replace(p, typedChoice='local_table_parser'), 'routine_intent')
        self.assertEqual(result.answer, d.TECH_TEMPLATE.format(choice='local_table_parser',
            technical_scope=h.scope.technical_scope, project=h.scope.project, phase=h.scope.phase))

    def test_exact_relay(self):
        h, r, p = fixture(True)
        result = self.run_case(h, r, p, 'routine_intent')
        self.assertEqual(result.answer, h.rules[0].decision.text)

    def test_all_dataclass_unknown_missing_duplicate_fields(self):
        h, r, p = fixture(True)
        schemas = [h, h.scope, h.source, h.input, h.rule_pins[0], h.rules[0],
                   h.rules[0].authority, h.rules[0].approval, h.rules[0].decision,
                   r, r.request, p, d.Intent('technical_choice', 'local_enum_parser', 'lead', 1),
                   d.Result(1, 'escalate', None, '', ('reason',), '{}', 0)]
        # Result.answer intentionally permits empty on escalation.
        for obj in schemas:
            data = asdict(obj)
            with self.subTest(schema=type(obj).__name__):
                with self.assertRaises(d.Invalid):
                    d.decode(type(obj), {**data, 'admin': True})
                with self.assertRaises(d.Invalid):
                    d.decode(type(obj), {k: v for k, v in data.items() if k != next(iter(data))})
                raw = d.canonical(obj)
                with self.assertRaises(d.Invalid):
                    d.decode(type(obj), raw[:-1] + ',"' + next(iter(data)) + '":null}')

    def test_proposal_cannot_mint_authority_or_clock(self):
        h, r, p = fixture()
        for key in ('issuer', 'evidence', 'scope', 'answer', 'target', 'nativeIDs',
                    'admin', 'approved', 'verified', 'now', 'ruleVersion'):
            with self.subTest(key=key):
                self.run_case(h, r, {**asdict(p), key: True})
        for value in ('false', 0, 1, None):
            self.run_case(h, r, {**asdict(p), 'uncertainty': value})
        self.run_case(h, r, replace(p, uncertainty=True))
        self.run_case(h, r, replace(p, escalationReasons=('hidden risk',)))
        self.run_case(h, r, replace(p, candidateRuleId='unknown'))
        self.run_case(h, r, replace(p, typedChoice='arbitrary command'))

    def test_nested_truthy_bools_versions_and_json_duplicates(self):
        h, r, p = fixture()
        for key in ('epoch',):
            self.run_case(replace(h, scope=replace(h.scope, **{key: True})), r, p)
        for key in ('epoch', 'durable_revision'):
            self.run_case(replace(h, input=replace(h.input, **{key: True})), r, p)
        for key in ('version', 'authority_revision', 'delegation_revision'):
            self.run_case(replace(h, rule_pins=(replace(h.rule_pins[0], **{key: True}),)), r, p)
        self.run_case(h, r, d.canonical(p)[:-1] + ',"uncertainty":false}')
        for raw in ('null', '[]', '{', '{"verified":true}', 'NaN'):
            self.run_case(h, r, raw)
        raw = d.canonical(h)
        self.run_case(raw.replace('"epoch":3', '"epoch":3,"epoch":3', 1), r, p)

    def test_reserved_always_escalates_even_valid_candidate(self):
        h, r, p = fixture()
        for flag in d.get_args(d.Reserved):
            rr = replace(r, request=replace(r.request, reserved=(flag,)))
            self.run_case(rebind(h, rr), rr, p)
        for kind in ('none', 'reserved', 'technical_your_call', 'human_approval'):
            rr = replace(r, request=replace(r.request, kind=kind))
            self.run_case(rebind(h, rr), rr, p)

    def test_strict_request_no_parameters_or_mixed_families(self):
        h, r, p = fixture()
        for key in ('command', 'paths', 'cost', 'service', 'parameters'):
            rr = asdict(r)
            rr['request'][key] = 'anything'
            self.run_case(h, rr, p)
        for key, value in [('decision_id', 'extra'), ('decision_revision', 1),
                           ('kind', 'recorded_technical_relay'), ('choices', ('copy_recorded_decision',))]:
            rr = replace(r, request=replace(r.request, **{key: value}))
            self.run_case(rebind(h, rr), rr, p)

    def test_host_input_current_state_failures(self):
        h, r, p = fixture()
        for key, value in [('sender', 'unknown'), ('project_path', '/fiction/elsewhere'),
                           ('epoch', 2), ('durable_revision', 0), ('report_id', 'other'),
                           ('report_sha256', 'b' * 64), ('received', '2030-01-01T00:00:00Z')]:
            self.run_case(replace(h, input=replace(h.input, **{key: value})), r, p)
        for key in ('project', 'lead', 'recipient', 'chief', 'phase', 'source_boundary', 'technical_scope'):
            self.run_case(replace(h, scope=replace(h.scope, **{key: 'rotated'})), r, p)
        self.run_case(replace(h, scope=replace(h.scope, epoch=4)), r, p)
        self.run_case(replace(h, source=replace(h.source, revision=8)), r, p)
        for observed in ('2026-10-18T12:01:00Z', '2026-10-18T11:00:00Z', '2026-10-18T12:00:00+00:00'):
            self.run_case(replace(h, observed=observed), r, p)
        self.run_case(h, r, p, now=NOW + timedelta(days=1))

    def test_rule_record_version_revocation_expiry_and_approval(self):
        h, r, p = fixture()
        rule = h.rules[0]
        variants = [replace(rule, version=True), replace(rule, version=2),
                    replace(rule, action_limit=2), replace(rule, template='Approved: {choice}'),
                    replace(rule, approval=replace(rule.approval, code_version='unreviewed')),
                    replace(rule, approval=replace(rule.approval, operator_record='')),
                    replace(rule, choices=('copy_recorded_decision',))]
        for field in ('authority', 'delegation'):
            for key, value in [('issuer', 'old-chief'), ('revocation_revision', 1), ('revision', 99),
                               ('expires', '2026-10-18T12:00:00Z'),
                               ('activates', '2026-10-19T00:00:00Z')]:
                variants.append(replace(rule, **{field: replace(getattr(rule, field), **{key: value})}))
        for rule in variants:
            with self.subTest(rule=rule):
                self.run_case(replace(h, rules=(rule,)), r, p)
        self.run_case(replace(h, rules=()), r, p)
        self.run_case(replace(h, rules=(h.rules[0], h.rules[0])), r, p)

    def test_relay_old_chief_revoked_late_wrong_destination_and_changed_text(self):
        h, r, p = fixture(True)
        dec = h.rules[0].decision
        variants = [replace(dec, text=dec.text + ' Publish too.'), replace(dec, kind='principal_approval')]
        for key, val in [('issuer', 'old-chief'), ('revocation_revision', 3), ('revision', 1),
                         ('expires', '2026-10-18T11:00:00Z')]:
            variants.append(replace(dec, record=replace(dec.record, **{key: val})))
        for key in ('project', 'recipient', 'chief', 'source_boundary'):
            variants.append(replace(dec, record=replace(dec.record,
                scope=replace(dec.record.scope, **{key: 'other'}))))
        for dec in variants:
            self.run_case(replace(h, rules=(replace(h.rules[0], decision=dec),)), r, p)
        self.run_case(replace(h, current_decision_revision=3), r, p)
        self.run_case(replace(h, current_decision_item='later-human-wait'), r, p)

    def test_semantic_miss_is_not_deterministic_proof(self):
        h, r, p = fixture()
        r = replace(r, body='Milestone done. The only source copy was lost; continue quietly.')
        # Deliberately bad classifier hides body risk. Schema CANNOT prove safety.
        self.run_case(rebind(h, r), r, p, 'routine_intent')

    def test_no_outward_io_or_admin_dependencies(self):
        tree = ast.parse(Path(d.__file__).read_text())
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imports, {'dataclasses', 'datetime', 'hashlib', 'json', 're', 'typing'})
        calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertFalse(set(calls) & {'open', 'eval', 'exec', '__import__'})

    def test_corpus_shape_and_honest_metrics(self):
        corpus = json.loads(Path(__file__).with_name('desk-bounded-corpus-v1.json').read_text())
        self.assertEqual(corpus['labeler'], 'STRONG-source-labelled-not-model-evaluated')
        self.assertIsNone(corpus['actual_model_metrics'])
        cases = corpus['cases']
        old = json.loads(Path(__file__).with_name('desk-corpus.json').read_text())
        self.assertEqual({c['legacy_id'] for c in cases if c['legacy_id']}, {c['id'] for c in old})
        self.assertGreater(len(cases), 22)
        self.assertEqual(len(cases), len({c['id'] for c in cases}))
        for c in cases:
            self.assertTrue(c['rationale'] and c['evidence_rules'])
            self.assertIn(c['split'], ('development', 'heldout'))
            self.assertIn(c['semantic_expected'], ('routine', 'escalate', 'filing_only'))
            self.assertIn(c['adversarial_engine_expected'], ('routine_intent', 'escalate'))
            self.assertEqual(c['semantic_miss_if_bad_proposal_passes'],
                c['semantic_expected'] == 'escalate' and c['adversarial_engine_expected'] == 'routine_intent')

    def test_corpus_adversarial_proposals_against_engine(self):
        corpus = json.loads(Path(__file__).with_name('desk-bounded-corpus-v1.json').read_text())
        for case in corpus['cases']:
            with self.subTest(case=case['id']):
                profile = case['profile']
                relay = profile in ('relay', 'wrong_project', 'late', 'destination')
                h, r, p = fixture(relay, report_id=case['id'])
                r = replace(r, body=case['text'])
                if profile == 'filing':
                    r = replace(r, request=replace(r.request, kind='none', choices=()))
                if profile == 'reserved':
                    r = replace(r, request=replace(r.request, reserved=('risk',)))
                if profile == 'unknown_type':
                    r = replace(r, request=replace(r.request, kind='technical_your_call'))
                h = rebind(h, r)
                if profile in ('unknown_sender', 'unknown_path', 'epoch'):
                    key, value = {'unknown_sender': ('sender', 'unknown'),
                                  'unknown_path': ('project_path', '/fiction/other'),
                                  'epoch': ('epoch', 2)}[profile]
                    h = replace(h, input=replace(h.input, **{key: value}))
                if profile in ('revoked', 'expired', 'old_chief'):
                    key, value = {'revoked': ('revocation_revision', 1),
                                  'expired': ('expires', '2026-10-18T12:00:00Z'),
                                  'old_chief': ('issuer', 'old-chief')}[profile]
                    rule = h.rules[0]
                    h = replace(h, rules=(replace(rule,
                        delegation=replace(rule.delegation, **{key: value})),))
                if profile in ('wrong_project', 'destination'):
                    rule = h.rules[0]
                    dec = rule.decision
                    key = 'project' if profile == 'wrong_project' else 'recipient'
                    dec = replace(dec, record=replace(dec.record,
                        scope=replace(dec.record.scope, **{key: 'other'})))
                    h = replace(h, rules=(replace(rule, decision=dec),))
                if profile == 'late':
                    h = replace(h, current_decision_item='later-human-wait')
                proposal_key = 'injected_target' if profile == 'injected_target' else 'relay' if relay else 'technical'
                p = corpus['adversarial_proposals'][proposal_key]
                self.run_case(h, r, p, case['adversarial_engine_expected'])


class BoundedParityTests(unittest.TestCase):
    def test_exact_22_outputs_17c8877(self):
        # Existing reviewed print-only export helper, private HOME from fixture.
        from hygiene_fixtures import outputs, pinned_print
        from test_modular import ModularTests, SRC
        ModularTests.setUp(self)
        baseline = self.root / 'bounded-baseline'
        before = outputs(pinned_print('17c8877', baseline, self.env), baseline, self.home)
        current = ModularTests.run_install(self, '--print')
        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertEqual(len(before), 22)
        self.assertEqual(before, outputs(current.stdout, SRC, self.home))
