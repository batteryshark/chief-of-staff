"""Offline bounded authority, v1. No transport, persistence, registry or admin API.

HostState MUST be constructed from current trusted native/ledger observations,
never from model/report JSON. Structural validation is NOT authentication. The
host owns code/approval records, clock, identities, scope and immutable sources.
The model can only propose; free prose semantic risk remains a model gate.
"""
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Literal, Union, get_args, get_origin, get_type_hints


CODE_VERSION = 'desk-bounded-v1'
Choice = Literal['local_enum_parser', 'local_table_parser', 'copy_recorded_decision']
Family = Literal['technical_choice', 'recorded_technical_relay']
Reserved = Literal['taste', 'scope', 'money', 'publication', 'destructive', 'hands',
                   'new_service', 'cross_project', 'priority', 'principal_approval', 'risk']
TECH_TEMPLATE = ('Choice: {choice}. Only the recorded internal local source-only '
                 'parser/validation scope {technical_scope}, project {project}, '
                 'phase {phase}. No other permission granted.')
RELAY_TEMPLATE = '{decision_text}'


@dataclass(frozen=True)
class Scope:
    project: str
    project_path: str
    lead: str
    recipient: str
    chief: str
    epoch: int
    phase: str
    source_boundary: str
    technical_scope: str


@dataclass(frozen=True)
class Source:
    ref: str
    sha256: str
    revision: int


@dataclass(frozen=True)
class Record:
    id: str
    revision: int
    issuer: str
    scope: Scope
    source: Source
    activates: str
    expires: str
    revocation_revision: int


@dataclass(frozen=True)
class Approval:
    operator_record: str
    strong_review_record: str
    code_version: str
    rule_id: str
    rule_version: int


@dataclass(frozen=True)
class Decision:
    record: Record
    item: str
    text: str
    text_sha256: str
    kind: Literal['pure_technical']


@dataclass(frozen=True)
class Rule:
    id: str
    version: int
    authority: Record
    delegation: Record
    approval: Approval
    family: Family
    choices: tuple[Choice, ...]
    action_limit: Literal[1]
    template: str
    decision: Union[Decision, None]


@dataclass(frozen=True)
class RulePin:
    id: str
    version: int
    authority_revision: int
    delegation_id: str
    delegation_revision: int


@dataclass(frozen=True)
class HostInput:
    receipt_id: str
    report_id: str
    report_sha256: str
    received: str
    sender: str
    project_path: str
    epoch: int
    durable_revision: int


@dataclass(frozen=True)
class HostState:
    scope: Scope
    source: Source
    input: HostInput
    observed: str
    rule_pins: tuple[RulePin, ...]
    rules: tuple[Rule, ...]
    current_decision_id: Union[str, None]
    current_decision_revision: int
    current_decision_item: Union[str, None]


@dataclass(frozen=True)
class Request:
    kind: Literal['technical_choice', 'recorded_technical_relay', 'none', 'reserved']
    choices: tuple[Choice, ...]
    decision_id: Union[str, None]
    decision_revision: int
    reserved: tuple[Reserved, ...]


@dataclass(frozen=True)
class Report:
    id: str
    observed: str
    scope: Scope
    body: str
    request: Request


@dataclass(frozen=True)
class Proposal:
    candidateRuleId: Union[str, None]
    typedChoice: Union[Choice, None]
    uncertainty: bool
    escalationReasons: tuple[str, ...]


@dataclass(frozen=True)
class Intent:
    family: Family
    choice: Choice
    recipient: str
    action_limit: Literal[1]


@dataclass(frozen=True)
class Result:
    schema_version: Literal[1]
    disposition: Literal['routine_intent', 'escalate']
    intent: Union[Intent, None]
    answer: str
    reasons: tuple[str, ...]
    evidence_json: str
    outward_effects: Literal[0]


class Invalid(ValueError):
    pass


def canonical(value):
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid('duplicate field: ' + key)
        result[key] = value
    return result


def decode(schema, value):
    """Strict exact fields/types, including nested records and duplicate JSON keys.

    Accept JSON text, a dict, or the exact frozen schema class. No coercions.
    Parsing HostState through this helper does not make a caller trusted.
    """
    if type(value) is str:
        try:
            value = json.loads(value, object_pairs_hook=_pairs)
        except (ValueError, RecursionError) as exc:
            raise Invalid('invalid JSON: ' + str(exc)) from exc
    return _typed(schema, value, schema.__name__)


def _typed(schema, value, path):
    origin, args = get_origin(schema), get_args(schema)
    if origin is Union:
        for member in args:
            try:
                return _typed(member, value, path)
            except Invalid:
                pass
        raise Invalid(path + ': invalid union')
    if origin is Literal:
        if not any(type(value) is type(a) and value == a for a in args):
            raise Invalid(path + ': unsupported value')
        return value
    if origin is tuple:
        if type(value) not in (list, tuple) or len(value) > 32:
            raise Invalid(path + ': bounded array required')
        result = tuple(_typed(args[0], v, path) for v in value)
        if len(set(result)) != len(result):
            raise Invalid(path + ': duplicate array entry')
        return result
    if is_dataclass(schema):
        if type(value) is schema:
            value = {f.name: getattr(value, f.name) for f in fields(schema)}
        names = get_type_hints(schema)
        if type(value) is not dict or set(value) != set(names):
            raise Invalid(path + ': missing/unknown fields')
        return schema(**{k: _typed(t, value[k], path + '.' + k) for k, t in names.items()})
    if type(value) is not schema:
        raise Invalid(path + ': wrong type')
    if schema is str:
        if not value.strip() and path != 'Result.answer':
            raise Invalid(path + ': nonempty text required')
        if len(value) > 12000 and path != 'Result.evidence_json':
            raise Invalid(path + ': bounded text required')
    if schema is int and (value < 0 or value > 2**53 - 1):
        raise Invalid(path + ': nonnegative bounded integer required')
    return value


def _utc(value):
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z', value):
        raise Invalid('canonical UTC required')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise Invalid('invalid UTC') from exc


def _require(condition, reason):
    if not condition:
        raise Invalid(reason)


def _id(value):
    _require(type(value) is str and
             re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value), 'invalid record/id')


def _record(record, host, now):
    _id(record.id)
    _require(record.issuer == host.scope.chief, 'issuer/current chief mismatch')
    _require(record.scope == host.scope, 'record scope/epoch/source boundary mismatch')
    _require(record.source == host.source, 'authoritative source changed')
    _require(record.revision > 0 and record.revocation_revision == 0, 'revoked/invalid record')
    _require(_utc(record.activates) <= now < _utc(record.expires), 'inactive/expired record')


def evaluate(host: HostState, report: Report, proposal: Proposal) -> Result:
    """Host entry; OS UTC only, no model/caller clock argument. No I/O/effects.

    Pure decision core is _evaluate_at. Time validity is necessarily conditional
    on trusted UTC. Same valid snapshot/report/proposal yields identical output;
    evaluation time is not minted into otherwise identical audit evidence.
    """
    return _evaluate_at(host, report, proposal, datetime.now(timezone.utc))


def _evaluate_at(host, report, proposal, now):
    # Private clock injection for offline tests only; never a model argument/tool.
    evidence = {'engine': CODE_VERSION}
    try:
        host = decode(HostState, host)
        report = decode(Report, report)
        proposal = decode(Proposal, proposal)
        evidence.update(host=asdict(host), report=asdict(report), proposal=asdict(proposal))
        _require(now.tzinfo is timezone.utc, 'host UTC clock required')
        _require(0 <= (now - _utc(host.observed)).total_seconds() <= 30,
                 'stale/future host observation')
        for name in ('project', 'lead', 'recipient', 'chief', 'phase',
                     'source_boundary', 'technical_scope'):
            _id(getattr(host.scope, name))
        path = host.scope.project_path
        _require(path.startswith('/') and all(p not in ('', '.', '..') for p in path.split('/')[1:]),
                 'canonical registered project path required')
        _id(host.source.ref)
        _require(re.fullmatch('[0-9a-f]{64}', host.source.sha256), 'invalid source hash')
        _require(host.source.revision > 0 and host.scope.epoch > 0, 'invalid source/epoch')
        inp = host.input
        _id(inp.receipt_id)
        _id(inp.report_id)
        _require(inp.durable_revision > 0, 'durable filing required')
        _require(inp.report_id == report.id and inp.report_sha256 == digest(report),
                 'report/durable receipt mismatch')
        _require(_utc(report.observed) <= _utc(inp.received) <= _utc(host.observed),
                 'future/mixed report clock')
        _require(report.scope == host.scope and inp.sender == host.scope.lead and
                 inp.project_path == host.scope.project_path and inp.epoch == host.scope.epoch,
                 'unknown/mixed sender/path/scope/epoch')
        req = report.request
        _require(not req.reserved and req.kind not in ('reserved', 'none'),
                 'reserved or unsupported request; filing is not disposition')
        _require(not proposal.uncertainty and not proposal.escalationReasons,
                 'model uncertainty/escalation')
        _require(proposal.candidateRuleId is not None, 'missing candidate rule')
        ids = [r.id for r in host.rules]
        pins = [p.id for p in host.rule_pins]
        _require(len(set(ids)) == len(ids) and len(set(pins)) == len(pins), 'duplicate rule id')
        _require(set(ids) == set(pins), 'unknown/missing rule pin')
        matches = [r for r in host.rules if r.id == proposal.candidateRuleId]
        _require(len(matches) == 1, 'unknown rule')
        rule = matches[0]
        _id(rule.id)
        pin = host.rule_pins[pins.index(rule.id)]
        _require((rule.version, rule.authority.revision, rule.delegation.id,
                  rule.delegation.revision) == (pin.version, pin.authority_revision,
                  pin.delegation_id, pin.delegation_revision) and rule.version > 0,
                 'rule/delegation version mismatch')
        approval = rule.approval
        _id(approval.operator_record)
        _id(approval.strong_review_record)
        _require((approval.rule_id, approval.rule_version, approval.code_version) ==
                 (rule.id, rule.version, CODE_VERSION), 'operator/Strong code approval mismatch')
        _record(rule.authority, host, now)
        _record(rule.delegation, host, now)
        _require(rule.family == req.kind, 'mixed request/rule family')
        _require(proposal.typedChoice in rule.choices and proposal.typedChoice in req.choices,
                 'choice outside enumerated delegation/request')
        if rule.family == 'technical_choice':
            _require(set(rule.choices) <= {'local_enum_parser', 'local_table_parser'} and
                     set(req.choices) <= {'local_enum_parser', 'local_table_parser'} and
                     rule.decision is None and req.decision_id is None and
                     req.decision_revision == 0 and rule.template == TECH_TEMPLATE,
                     'unsupported technical parameters/template')
            answer = TECH_TEMPLATE.format(choice=proposal.typedChoice,
                technical_scope=host.scope.technical_scope, project=host.scope.project,
                phase=host.scope.phase)
        else:
            _require(rule.choices == ('copy_recorded_decision',) and
                     req.choices == ('copy_recorded_decision',) and
                     rule.template == RELAY_TEMPLATE and rule.decision is not None,
                     'unsupported relay parameters/template')
            decision = rule.decision
            _id(decision.item)
            _record(decision.record, host, now)
            _require((decision.record.id, decision.record.revision, decision.item) ==
                     (host.current_decision_id, host.current_decision_revision,
                      host.current_decision_item) and
                     (req.decision_id, req.decision_revision) ==
                     (decision.record.id, decision.record.revision), 'late/stale decision')
            _require(text_hash(decision.text) == decision.text_sha256, 'decision text changed')
            answer = decision.text  # exact immutable copy; chief act != principal yes
        evidence.update(rule_id=rule.id, rule_version=rule.version,
                        authority_revision=rule.authority.revision)
        result = Result(1, 'routine_intent', Intent(rule.family, proposal.typedChoice,
                        host.scope.recipient, 1), answer, (), canonical(evidence), 0)
    except (Invalid, TypeError, ValueError, RecursionError) as exc:
        # Even malformed inputs retain a fingerprint, without reflecting attacker
        # supplied answer/target/admin fields into a constrained intent.
        for name, value in (('host', host), ('report', report), ('proposal', proposal)):
            if name not in evidence:
                try:
                    evidence[name + '_invalid_sha256'] = digest(value)
                except (TypeError, ValueError, RecursionError):
                    evidence[name + '_invalid_type'] = type(value).__name__
        result = Result(1, 'escalate', None, '', (str(exc),), canonical(evidence), 0)
    return decode(Result, result)
