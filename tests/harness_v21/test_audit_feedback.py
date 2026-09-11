"""Field feedback locates conflicts without relaxing validation or editing verdicts."""
from copy import deepcopy
import json
import pytest
from esr_harness.audit import (ModelAuditor, AuditConsistencyError, validate_report,
                               protocol_repair_message, literal_answer_packet, status,
                               ADMISSIBLE_REPAIR)
from esr_harness.protocol import HarnessError
from .helpers import env, opened, update
from .test_audit_spans import ReplyClient, fixture_report


def sample():
    h = env(); update(h, opened(h))
    return h, fixture_report(h)


@pytest.mark.parametrize('verdict', ['supported', 'unknown', 'contradicted'])
def test_all_conflicts_are_located_without_mutation(verdict):
    h, report = sample()
    for row in [report['target'], report['coverage'], *report['claims']]:
        row.update(status=verdict, need='A missing obligation' if verdict == 'supported' else '  ')
    original = deepcopy(report)
    with pytest.raises(AuditConsistencyError) as caught:
        validate_report(report, h.audit_packet(), h.observations)
    assert report == original
    error = caught.value
    assert [p['path'] for p in error.problems] == [
        'audit.target.need', 'audit.coverage.need', 'audit.claims[0].need']
    assert all(p['status_path'] == p['path'].replace('.need', '.status') for p in error.problems)
    assert all(p['status'] == verdict for p in error.problems)
    assert str(error) == error.problems[0]['rule']


@pytest.mark.parametrize('profile', ['atomic', 'task_first_literal'])
def test_only_repair_feedback_changes_and_valid_negative_survives(profile):
    h, good = sample()
    good['coverage'].update(status='contradicted', need='The answer must include two values')
    bad = deepcopy(good); bad['coverage']['need'] = ''
    clients = [ReplyClient([bad, good]) for _ in range(2)]
    auditors = [ModelAuditor(c, profile=profile, repair_feedback=f)
                for c, f in zip(clients, ['generic', 'field_paths'])]
    before = deepcopy((h.audit_packet(), h.observations))
    results = [a.audit(h.question, h.audit_packet(), list(h.observations.values())) for a in auditors]
    assert results == [good, good] and status(results[1]) == 'contradicted'
    assert (h.audit_packet(), h.observations) == before
    assert clients[0].messages[0] == clients[1].messages[0]
    assert clients[0].messages[1][:-1] == clients[1].messages[1][:-1]
    assert clients[0].messages[1][-1]['content'] == (
        'Repair protocol only; keep all original evidence: Unresolved verdict requires a concrete need')
    assert 'audit.coverage.need' in clients[1].messages[1][-1]['content']
    assert auditors[0].identity != auditors[1].identity
    assert auditors[0].identity['system_hash'] == auditors[1].identity['system_hash']


@pytest.mark.parametrize('feedback', ['generic', 'field_paths', 'admissible'])
def test_invalid_repair_still_fails_after_one_attempt(feedback):
    h, bad = sample(); bad['target'].update(status='contradicted', need='')
    c = ReplyClient([bad, bad])
    with pytest.raises(HarnessError, match='Unresolved verdict'):
        ModelAuditor(c, repair_feedback=feedback).audit(h.question, h.audit_packet(), list(h.observations.values()))
    assert len(c.messages) == 2


def test_other_error_classes_retain_feedback_and_validation_order():
    h, bad = sample()
    bad['target'].update(status='supported', need='Missing condition')
    bad['claims'][0]['claim_id'] = 'invented'
    with pytest.raises(HarnessError, match='expected exactly') as caught:
        validate_report(bad, h.audit_packet(), h.observations)
    assert not isinstance(caught.value, AuditConsistencyError)
    assert protocol_repair_message(caught.value, 'generic') == protocol_repair_message(caught.value, 'field_paths')


@pytest.mark.parametrize('answer', ['Aven Mor', '"Aven Mor"', '  Aven\n', 'BEGIN_ANSWER_x\nEND_ANSWER_x'])
def test_restored_literal_rendering_preserves_all_characters(answer):
    payload = {'question': 'Return a name.', 'answer': answer, 'claims': [], 'observations': []}
    before = deepcopy(payload)
    candidate, serialized = literal_answer_packet(payload).split('\n\nAudit inputs (candidate answer above):\n')
    begin, body = candidate.split('\n', 1)
    actual, end = body.rsplit('\n', 1)
    assert begin.startswith('BEGIN_ANSWER_') and end.startswith('END_ANSWER_')
    assert actual == answer and actual not in {begin, end}
    assert json.loads(serialized) == {k: v for k, v in payload.items() if k != 'answer'}
    assert payload == before


def test_valid_report_gets_no_extra_inference_or_intervention():
    h, good = sample()
    clients = [ReplyClient([good]) for _ in range(2)]
    reports = [ModelAuditor(c, repair_feedback=f).audit(h.question, h.audit_packet(), list(h.observations.values()))
               for c, f in zip(clients, ['generic', 'field_paths'])]
    assert reports == [good, good] and all(len(c.messages) == 1 for c in clients)
    assert clients[0].messages == clients[1].messages


def test_unknown_feedback_fails_before_inference():
    c = ReplyClient([])
    with pytest.raises(ValueError, match='Unknown audit repair feedback'):
        ModelAuditor(c, repair_feedback='unbounded')
    assert c.messages == []


@pytest.mark.parametrize('verdict', ['supported', 'unknown', 'contradicted'])
def test_admissible_feedback_adds_rules_without_choosing_a_verdict(verdict):
    h, good = sample()
    good['coverage'].update(status=verdict, need='' if verdict == 'supported' else 'The second required item is missing')
    bad = deepcopy(good)
    bad['coverage']['need'] = 'A missing obligation' if verdict == 'supported' else ''
    clients = [ReplyClient([bad, good]) for _ in range(2)]
    auditors = [ModelAuditor(c, repair_feedback=f) for c, f in zip(clients, ['field_paths', 'admissible'])]
    reports = [a.audit(h.question, h.audit_packet(), list(h.observations.values())) for a in auditors]
    assert reports == [good, good]
    assert clients[0].messages[0] == clients[1].messages[0]
    assert clients[0].messages[1][:-1] == clients[1].messages[1][:-1]
    assert clients[1].messages[1][-1]['content'] == clients[0].messages[1][-1]['content'] + ADMISSIBLE_REPAIR
    assert auditors[0].identity['system_hash'] == auditors[1].identity['system_hash']
    assert auditors[0].identity['schema_hash'] == auditors[1].identity['schema_hash']
    assert auditors[0].identity != auditors[1].identity


def test_admissible_rules_cannot_repair_other_errors_or_add_a_call():
    error = HarnessError('protocol_error', 'Wrong claim ID')
    assert protocol_repair_message(error, 'admissible') == protocol_repair_message(error, 'generic')
    h, good = sample()
    clients = [ReplyClient([good]) for _ in range(2)]
    for c, feedback in zip(clients, ['field_paths', 'admissible']):
        assert ModelAuditor(c, repair_feedback=feedback).audit(h.question, h.audit_packet(), list(h.observations.values())) == good
    assert clients[0].messages == clients[1].messages and len(clients[0].messages) == 1
