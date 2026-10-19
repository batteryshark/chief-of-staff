"""Pure questions-only eligibility; observations/classifications are not auth."""
import hashlib
import re


def questions(report):
    value = report.get('questions')
    if not isinstance(value, list) or not all(isinstance(q, str) for q in value):
        raise ValueError('STOP unknown question source')
    return list(dict.fromkeys(q for q in value if q.strip()))


def normalized(text):
    return ' '.join(text.casefold().split())


def reviewed_questions(report, evidence, open_text, source_sha256):
    """Validate retained REVIEW OBSERVATIONS, not native identity or meaning proof.

    The reviewer explicitly binds a verbatim question to a scoped current excerpt;
    rewording is the reviewer's observation, never inferred by this helper.
    """
    if not isinstance(evidence, list):
        return set(), False
    known = set()
    for item in evidence:
        if not isinstance(item, dict):
            return set(), False
        excerpt = item.get('excerpt')
        if (item.get('question') not in questions(report)
                or item.get('project') != report.get('project')
                or item.get('lead_session') != report.get('lead_session')
                or item.get('basis') != 'current_chief_open'
                or item.get('source_sha256') != source_sha256
                or not isinstance(excerpt, str) or not excerpt.strip()
                or excerpt not in open_text
                or not all(isinstance(report.get(k), str) and report[k]
                           and re.search(r'(?<![\w/.-])' + re.escape(report[k]) + r'(?![\w/.-])', excerpt)
                           for k in ('project', 'lead_session'))):
            return set(), False
        known.add(item['question'])
    return known, True


def review(report, receipts, expected_source, source, open_text, source_sha256, classification, evidence=None):
    qs = questions(report)
    if not qs:
        return {'state': 'deduplicated', 'reason': 'questions[] empty; your_part is status only'}
    if source != expected_source or not isinstance(open_text, str) or source_sha256 != hashlib.sha256(open_text.encode()).hexdigest():
        return {'state': 'pending', 'reason': 'wrong/unknown current chief-open source'}
    known = set()
    uncertain_suppression = False
    for receipt in receipts.values():
        prior_report = receipt.get('report', {})
        if not all(isinstance(report.get(k), str) and report[k] and prior_report.get(k) == report[k]
                   for k in ('project', 'lead_session')):
            continue
        prior = questions(prior_report)
        if receipt.get('suppressed_actions') and any(normalized(q) == normalized(old) for q in qs for old in prior):
            uncertain_suppression = True
        sent = any(i.get('action', {}).get('type') == 'forward' and i.get('result', {}).get('dispatched') is True
                   for i in receipt.get('completed', []))
        if sent:
            known.update(q for q in qs if any(normalized(q) == normalized(old) for old in prior))
        # Old suppression reasons/classifications alone are never conclusive.
        retained = receipt.get('question_review', {})
        if retained.get('source') == source and retained.get('source_sha256') == source_sha256:
            covered, valid = reviewed_questions(report, retained.get('evidence'), open_text, source_sha256)
            if valid:
                known.update(covered)
    covered, valid = reviewed_questions(report, [] if evidence is None else evidence, open_text, source_sha256)
    if not valid:
        return {'state': 'pending', 'reason': 'invalid question-specific current-source review evidence'}
    known.update(covered)
    observation = {'source': source, 'source_sha256': source_sha256, 'evidence': evidence or []}
    if known and len(known) < len(qs):
        return {**observation, 'state': 'pending', 'reason': 'mixed known/new questions require operator review; no duplicate or lost question'}
    if known:
        return {**observation, 'state': 'deduplicated', 'reason': 'all questions covered by same-scope completed forwards or reviewed current-source evidence'}
    if uncertain_suppression or classification == 'already_open' or any(normalized(q) in normalized(open_text) for q in qs):
        return {**observation, 'state': 'pending', 'reason': 'candidate known question requires precise scoped review evidence'}
    if classification != 'new_unasked':
        return {'state': 'pending', 'reason': 'new/unasked status not established'}
    return {'state': 'eligible', 'reason': 'explicit questions reviewed new/unasked; no answer authority'}
