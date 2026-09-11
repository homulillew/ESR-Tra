"""String facts assist the auditor without deriving requirements or verdicts."""
from copy import deepcopy
import json
import pytest
from esr_harness.audit import ModelAuditor, answer_surface, ANSWER_SURFACE_SYSTEM
from esr_harness.audit_spans import source_span_packet
from esr_harness.protocol import HarnessError
from .helpers import env, opened, update
from .test_audit_spans import ReplyClient, fixture_report


@pytest.mark.parametrize('answer,length,first,last,count,start,end', [
    ('"Aven Mor"', 10, 'U+0022', 'U+0022', 2, True, True),
    ('Aven Mor', 8, 'U+0041', 'U+0072', 0, False, False),
    (' "A"\n', 5, 'U+0020', 'U+000A', 2, False, False),
    ('\u201cA\u201d', 3, 'U+201C', 'U+201D', 0, False, False),
    ('\U0001f642', 1, 'U+1F642', 'U+1F642', 0, False, False),
    ('', 0, None, None, 0, False, False),
    ('"', 1, 'U+0022', 'U+0022', 1, True, True),
])
def test_surface_is_exact_codepoint_data(answer, length, first, last, count, start, end):
    assert answer_surface(answer) == {
        'length_codepoints': length, 'first_codepoint': first, 'last_codepoint': last,
        'ascii_double_quote_count': count, 'starts_with_ascii_double_quote': start,
        'ends_with_ascii_double_quote': end}


def test_unbound_answer_remains_distinct_from_an_empty_string():
    assert answer_surface(None) is None
    assert answer_surface('') is not None


@pytest.mark.parametrize('verdict', ['supported', 'unknown', 'contradicted'])
def test_surface_changes_only_derived_input_and_explanation(verdict):
    h = env(); update(h, opened(h))
    views = list(h.observations.values()); packet = h.audit_packet()
    packet['answer'] = '"Taylor"'
    _, refs = source_span_packet(views)
    wire = fixture_report(h)
    wire['claims'][0]['quotes'] = [{'span_id': next(iter(refs))}]
    wire['coverage'].update(status=verdict, need='' if verdict == 'supported' else 'A task obligation remains unsatisfied')
    before = deepcopy((packet, views))
    clients = [ReplyClient([wire]) for _ in range(2)]
    auditors = [ModelAuditor(c, citation_mode='source_spans', profile=p, repair_feedback='admissible')
                for c, p in zip(clients, ['task_first_literal', 'task_first_literal_surface'])]
    reports = [a.audit(h.question, packet, views) for a in auditors]
    assert reports[0] == reports[1] and reports[1]['coverage']['status'] == verdict
    assert (packet, views) == before
    split = '\n\nAudit inputs (candidate answer above):\n'
    old_candidate, old_json = clients[0].messages[0][1]['content'].split(split)
    new_candidate, new_json = clients[1].messages[0][1]['content'].split(split)
    old, new = json.loads(old_json), json.loads(new_json)
    assert new.pop('answer_surface') == answer_surface(packet['answer'])
    assert old == new and old_candidate == new_candidate
    old_system, old_schema = clients[0].messages[0][0]['content'].split('\nSchema:\n')
    new_system, new_schema = clients[1].messages[0][0]['content'].split('\nSchema:\n')
    assert old_schema == new_schema and new_system == old_system + ANSWER_SURFACE_SYSTEM
    assert auditors[0].identity != auditors[1].identity
    assert len(clients[0].messages) == len(clients[1].messages) == 1


def test_surface_cannot_promote_an_invalid_report_or_add_retries():
    h = env(); update(h, opened(h)); bad = fixture_report(h)
    bad['coverage'].update(status='contradicted', need='')
    c = ReplyClient([bad, bad])
    with pytest.raises(HarnessError, match='Unresolved verdict'):
        ModelAuditor(c, profile='task_first_literal_surface', repair_feedback='admissible').audit(
            h.question, h.audit_packet(), list(h.observations.values()))
    assert len(c.messages) == 2 and c.messages[1][:2] == c.messages[0]
