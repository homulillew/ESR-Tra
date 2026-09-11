import pytest
from esr_harness_v3 import Config, Harness
from esr_harness_v3.adapters import MemoryRetriever
from esr_harness_v3.protocol import canonical
from .conftest import DOCS, AuditFixture, add, send, source


@pytest.fixture
def audited():
    a = AuditFixture()
    h = Harness('Who won?', MemoryRetriever(DOCS), auditor=a)
    yield h, a
    h.close()


def test_explicit_audit_without_draft(audited):
    h, a = audited
    source(h)
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert r['ok'] and h.state['draft'] is None and len(a.calls) == 1
    assert h.state['feedback']['answer'] == 'A'


def test_empty_audit_is_local_error(audited):
    h, a = audited
    r = send(h, ('verify_answer', {}))[0]
    assert r['code'] == 'no_candidate' and a.calls == []


def test_audit_draft(audited):
    h, a = audited
    source(h)
    send(h, ('update_state', {'draft': {'answer': 'A', 'refs': ['this']}}))
    assert send(h, ('verify_answer', {}))[0]['ok']


def test_own_update_draft_and_verify_same_response(audited):
    h, a = audited
    source(h)
    rows = send(h, [('update_state', {'draft': {'answer': 'A', 'refs': ['this']}}), ('verify_answer', {})])
    assert all(r['ok'] for r in rows)


def test_exact_alias_and_explicit_ref_share_audit(audited):
    h, a = audited
    oid = source(h)
    assert send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]['ok']
    r = send(h, ('submit_answer', {'answer': 'A', 'refs': [oid]}))[0]
    assert r['terminal']['audit_status'] == 'supported'


def test_audit_a_does_not_certify_b(audited):
    h, a = audited
    oid = source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))
    r = send(h, ('submit_answer', {'answer': 'B', 'refs': [oid]}))[0]
    assert r['terminal']['audit_status'] == 'unverified'


def test_literal_quotes_not_normalized(audited):
    h, a = audited
    oid = source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))
    r = send(h, ('submit_answer', {'answer': '"A"', 'refs': [oid]}))[0]
    assert r['terminal']['answer'] == '"A"'
    assert r['terminal']['audit_status'] == 'unverified'


def test_verify_has_real_feedback_boundary(audited):
    h, a = audited
    source(h)
    r = send(h, [('verify_answer', {'answer': 'A', 'refs': ['this']}),
                 ('submit_answer', {'answer': 'A', 'refs': ['this']})])
    assert r[0]['ok'] and r[1]['code'] == 'not_executed' and h.terminal is None
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]['ok']


def test_same_packet_cache_no_remote_request(audited):
    h, a = audited
    oid = source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))[0]
    assert r['cached'] and len(a.calls) == 1


def test_denial_not_washed_by_clear_draft():
    a = AuditFixture(('contradicted',))
    h = Harness('Q', MemoryRetriever(DOCS), auditor=a)
    oid = source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))
    send(h, ('update_state', {'draft': None}))
    r = send(h, ('submit_answer', {'answer': 'A', 'refs': [oid]}))[0]
    assert r['terminal']['audit_status'] == 'contradicted'
    assert h.state['conflicts']
    h.close()


def test_denial_with_paragraph_ref_still_matches():
    def response(p):
        ref = next(r for r in p['raw_sources'] if ':p' in r)
        return canonical({'checks': {k: {'verdict': 'contradicted', 'explanation': 'Fixture disagreement', 'refs': [ref]}
                                     for k in p['expected_checks']}})
    h = Harness('Q', MemoryRetriever(DOCS), auditor=AuditFixture(callback=response))
    oid = source(h)
    assert send(h, ('verify_answer', {'answer': 'A', 'refs': [oid]}))[0]['ok']
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': [oid]}))[0]['terminal']['audit_status'] == 'contradicted'
    h.close()


def test_noop_target_effect_not_global_progress():
    h = Harness('Return a quoted name', MemoryRetriever(DOCS), auditor=AuditFixture(('contradicted',)))
    source(h)
    send(h, ('update_state', {'draft': {'answer': 'A', 'refs': ['this']}}))
    send(h, ('verify_answer', {}))
    send(h, ('update_state', {'focus': 'I will fix the quotes now'}))
    feedback = h.state['feedback']
    assert feedback['actual_effects']['answer_changed'] is False
    assert feedback['actual_effects']['focus_changed'] is True
    assert feedback['answer_surface']['ascii_double_quotes'] == 0
    h.close()


def test_repair_preserves_packet_and_caps_attempts():
    a = AuditFixture(('malformed', 'supported'))
    h = Harness('Q', MemoryRetriever(DOCS), auditor=a)
    source(h)
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert r['ok'] and len(a.calls) == 2
    assert a.calls[0]['messages'][:2] == a.calls[1]['messages'][:2]
    h.close()


def test_protocol_failure_never_creates_semantic_conflict():
    a = AuditFixture(('malformed',))
    h = Harness('Q', MemoryRetriever(DOCS), auditor=a)
    source(h)
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert r['code'] == 'audit_protocol_error' and len(a.calls) == 2
    assert not h.state['conflicts'] and not h.state['audits']
    h.close()


def test_audit_budget_reserves_a_reaction():
    a = AuditFixture()
    h = Harness('Q', MemoryRetriever(DOCS), auditor=a, config=Config(max_model_calls=5, audit_attempts=2))
    source(h)
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert r['code'] == 'audit_budget' and len(a.calls) == 0
    assert h.state['model_calls'] == 3
    h.close()


@pytest.mark.parametrize('content', ['{"checks":{}}', '{"checks":{"target":{"verdict":"supported","explanation":"x","refs":[]}}}',
    '{"checks":{"target":{"verdict":"supported","explanation":"x","refs":[]},"coverage":{"verdict":"supported","explanation":"x","refs":["o99"]}}}'])
def test_empty_incomplete_or_foreign_checks_rejected(content):
    a = AuditFixture(callback=lambda p: content)
    h = Harness('Q', MemoryRetriever(DOCS), auditor=a)
    source(h)
    assert send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]['code'] == 'audit_protocol_error'
    assert not h.state['audits']
    h.close()


def test_claim_audit_requires_own_lineage():
    def response(p):
        report = {'checks': {k: {'verdict': 'supported', 'explanation': 'Fixture', 'refs': []} for k in p['expected_checks']}}
        for k in p['expected_checks']:
            if k.startswith('c') and k != 'coverage':
                report['checks'][k]['refs'] = ['o2']  # c1 actually uses o1.
        return canonical(report)
    h = Harness('Q', MemoryRetriever(DOCS), auditor=AuditFixture(callback=response))
    source(h); c1 = add(h)
    send(h, ('open_page', {'ref': 'd2'}))
    r = send(h, ('verify_answer', {'answer': 'A', 'refs': [c1, 'o2']}))[0]
    assert r['code'] == 'audit_protocol_error'
    h.close()


def test_hard_mode_requires_matching_pass():
    h = Harness('Q', MemoryRetriever(DOCS), auditor=AuditFixture(), config=Config(audit_mode='hard', require_sources=True))
    source(h)
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]['code'] == 'audit_required'
    assert send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))[0]['ok']
    assert send(h, ('submit_answer', {'answer': 'B', 'refs': ['this']}))[0]['code'] == 'audit_required'
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]['ok']
    h.close()


def test_hard_mode_does_not_turn_unknown_into_supported():
    h = Harness('Q', MemoryRetriever(DOCS), auditor=AuditFixture(('unknown',)), config=Config(audit_mode='hard'))
    source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]['code'] == 'audit_required'
    h.close()


def test_feedback_keeps_audited_and_current_answer_distinct(audited):
    h, a = audited
    source(h)
    send(h, ('verify_answer', {'answer': 'A', 'refs': ['this']}))
    send(h, ('update_state', {'draft': {'answer': '"B"', 'refs': ['this']}}))
    feedback = h.state['feedback']
    assert feedback['answer'] == 'A'
    assert feedback['answer_surface']['ascii_double_quotes'] == 0
    assert feedback['current_draft_answer'] == '"B"'
    assert feedback['current_draft_surface']['ascii_double_quotes'] == 2
