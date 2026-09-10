"""Task-first review changes instructions, never the evidence or model verdict."""
from copy import deepcopy
import json
import pytest
from esr_harness.audit import ModelAuditor, status
from esr_harness.audit_spans import source_span_packet
from esr_harness.prompts import AUDIT_SPAN_SYSTEM, TASK_FIRST_AUDIT
from esr_harness.protocol import HarnessError
from .helpers import env, opened, update
from .test_audit_spans import ReplyClient, fixture_report


@pytest.mark.parametrize('verdict', ['supported', 'contradicted', 'unknown'])
def test_profiles_send_identical_evidence_and_preserve_verdict(verdict):
    h = env(); update(h, opened(h))
    views = list(h.observations.values())
    packet = h.audit_packet()
    wire = fixture_report(h)
    _, refs = source_span_packet(views)
    wire['claims'][0]['quotes'] = [{'span_id': next(iter(refs))}]
    wire['coverage'].update(status=verdict, need='' if verdict == 'supported' else 'Return two ordered values')
    before = deepcopy((packet, views))
    clients = [ReplyClient([wire]), ReplyClient([wire])]
    auditors = [ModelAuditor(c, citation_mode='source_spans', profile=p)
                for c, p in zip(clients, ['atomic', 'task_first'])]
    reports = [a.audit(h.question, packet, views) for a in auditors]
    assert reports[0] == reports[1] and status(reports[1]) == verdict
    assert clients[0].messages[0][1:] == clients[1].messages[0][1:]
    assert clients[0].messages[0][0]['content'].split('\nSchema:\n')[1] == clients[1].messages[0][0]['content'].split('\nSchema:\n')[1]
    assert auditors[0].system == AUDIT_SPAN_SYSTEM
    assert auditors[1].system == TASK_FIRST_AUDIT + AUDIT_SPAN_SYSTEM
    assert auditors[0].identity['system_hash'] != auditors[1].identity['system_hash']
    assert auditors[0].identity['schema_hash'] == auditors[1].identity['schema_hash']
    assert json.loads(clients[1].messages[0][1]['content'])['question'] == h.question
    assert (packet, views) == before


def test_task_first_preserves_bounded_protocol_failure():
    h = env(); update(h, opened(h))
    c = ReplyClient([{}, {}])
    with pytest.raises(HarnessError):
        ModelAuditor(c, profile='task_first').audit(h.question, h.audit_packet(), list(h.observations.values()))
    assert len(c.messages) == 2 and c.messages[1][:2] == c.messages[0]


def test_unknown_profile_fails_before_inference():
    c = ReplyClient([])
    with pytest.raises(ValueError, match='Unknown auditor profile'):
        ModelAuditor(c, profile='typo')
    assert c.messages == []
