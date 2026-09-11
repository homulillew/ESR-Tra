from copy import deepcopy
from dataclasses import replace
import pytest
from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import MemoryRetriever
from esr_harness_v3.protocol import canonical
from esr_harness_v3.state import claim_sources
from .conftest import DOCS, AuditFixture, add, send, source


def test_exposure_requires_response(h):
    oid = source(h)
    assert oid not in h.state['exposed']
    decision = h.begin()
    assert decision.binding['this'] == oid
    assert oid not in h.state['exposed']
    send_msg = {'role': 'assistant', 'tool_calls': [{'id': 't', 'type': 'function', 'function': {
        'name': 'submit_answer', 'arguments': canonical({'answer': 'A', 'refs': ['this']})}}]}
    h.respond(decision, send_msg)
    assert oid in h.state['exposed']


def test_q790_unused_source_and_null_focus_do_not_block(h):
    o1 = source(h)
    o2 = send(h, ('open_page', {'ref': 'd2'}))[0]['observation']['observation']
    send(h, ('update_state', {'focus': None}))
    result = send(h, ('submit_answer', {'answer': 'A', 'refs': [o2]}))[0]
    assert result['ok'] and result['terminal']['basis']['sources'] == [o2]
    assert o1 in h.state['observations']


def test_read_unregistered_without_focus(h):
    oid = source(h)
    send(h, ('update_state', {'focus': None, 'note': 'not using the page'}))
    r = send(h, ('read_evidence', {'ref': oid}))[0]
    assert r['ok'] and r['observation']['text'] == h.state['observations'][oid]['text']


def test_add_allocates_and_returns_content_mapping(h):
    source(h)
    c = add(h)
    assert c == 'c1' and h.state['claims'][c]['finding'] == 'A fact'
    assert h.state['published_claims'] == {}
    send(h, ('update_state', {'focus': 'Continue without a claim pointer'}))
    assert h.state['published_claims'][c] == 1


def test_guess_new_claim_same_response_rejected(h):
    source(h)
    rows = send(h, [('update_state', {'add': [{'requirement': 'r', 'finding': 'f', 'refs': ['this']}]}),
                    ('submit_answer', {'answer': 'A', 'refs': ['c1']})])
    assert rows[0]['ok'] and rows[1]['code'] == 'unpublished_claim'
    assert h.terminal is None


def test_new_observation_same_response_rejected(h):
    send(h, ('search', {'query': 'tournament'}))
    rows = send(h, [('open_page', {'ref': 'd1'}), ('submit_answer', {'answer': 'A', 'refs': ['o1']})])
    assert rows[1]['code'] == 'unexposed_reference'
    assert h.terminal is None


def test_new_document_same_response_rejected(h):
    rows = send(h, [('search', {'query': 'tournament'}), ('open_page', {'ref': 'd1'})])
    assert rows[0]['ok'] and rows[1]['code'] == 'unpublished_document'


def test_multi_read_disables_this(h):
    send(h, ('search', {'query': 'tournament'}))
    rows = send(h, [('open_page', {'ref': 'd1'}), ('open_page', {'ref': 'd2'})])
    assert all(r['ok'] for r in rows)
    r = send(h, ('update_state', {'add': [{'requirement': 'r', 'finding': 'f', 'refs': ['this']}]}))[0]
    assert r['code'] == 'this_unavailable'


def test_failed_read_clears_old_this(h):
    source(h)
    send(h, ('open_page', {'ref': 'd999'}))
    result = send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert result['code'] == 'this_unavailable'


def test_this_persists_through_pure_repair_when_rendered(h):
    oid = source(h)
    send(h, ('update_state', {'add': [{'claim': 'c9', 'requirement': 'r', 'finding': 'f', 'refs': ['this']}]}))
    c = add(h)
    assert h.state['claims'][c]['direct_refs'] == [oid]


def test_this_frozen_despite_later_open(h):
    old = source(h)
    result = send(h, [('open_page', {'ref': 'd2'}),
                      ('update_state', {'add': [{'requirement': 'r', 'finding': 'f', 'refs': ['this']}]})])
    assert result[1]['ok']
    assert h.state['claims']['c1']['direct_refs'] == [old]
    assert h.state['this_candidate'] != old


def test_this_disabled_config():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(enable_this=False))
    oid = source(h)
    result = send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]
    assert result['code'] == 'this_unavailable'
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': [oid]}))[0]['ok']
    h.close()


def test_this_and_explicit_selector_deduplicate_but_keep_trace(h):
    oid = source(h)
    result = send(h, ('submit_answer', {'answer': 'A', 'refs': ['this', oid]}))[0]
    assert result['terminal']['basis']['sources'] == [oid]
    assert len(result['terminal']['basis']['trace']) == 2


def test_derived_claim_no_duplicate_raw_ids(h):
    oid = source(h)
    c1 = add(h)
    c2 = add(h, 'Derived', refs=[c1])
    record = h.state['claims'][c2]
    assert record['direct_refs'] == []
    assert claim_sources(h.state, c2, 1) == [oid]


def test_requirement_only_invalidates_finding(h):
    source(h); c1 = add(h)
    r = send(h, ('update_state', {'revise': [{'claim': c1, 'requirement': 'New condition'}]}))[0]
    assert r['ok'] and h.state['claims'][c1]['finding'] == ''
    assert h.state['claim_history'][c1]['1']['finding'] == 'A fact'


def test_local_dependency_invalidation_preserves_independent(h):
    oid = source(h); c1 = add(h); c2 = add(h, 'Derived', refs=[c1]); c3 = add(h, 'Independent', refs=[oid])
    send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'Revised', 'refs': [oid]}]}))
    assert c2 in h.state['invalid'] and c3 not in h.state['invalid']
    assert oid in h.state['observations']
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': [c2]}))[0]['code'] == 'stale_claim'


def test_revision_cuts_old_segment_not_raw_archive(h):
    oid = source(h); c1 = add(h)
    old_segment = h.state['segment']
    send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'Changed', 'refs': [oid]}]}))
    assert h.state['segment'] > old_segment
    assert len(h.state['history']) == 1
    assert h.state['observations'][oid]['text']


def test_source_only_addition_preserves_dependency(h):
    o1 = source(h); c1 = add(h); c2 = add(h, 'Derived', refs=[c1])
    o2 = send(h, ('open_page', {'ref': 'd2'}))[0]['observation']['observation']
    send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'A fact', 'refs': [o1, o2]}]}))
    assert h.state['claims'][c1]['meaning_version'] == 1
    assert c2 not in h.state['invalid']
    assert claim_sources(h.state, c2, 1) == [o1]  # No retrospective source laundering.


def test_atomic_multi_revision_binds_proposal_version(h):
    oid = source(h); c1 = add(h); c2 = add(h, 'Derived', refs=[c1])
    result = send(h, ('update_state', {'revise': [
        {'claim': c2, 'finding': 'New derivation', 'refs': [c1]},
        {'claim': c1, 'finding': 'New premise', 'refs': [oid]}]}))[0]
    assert result['ok'], result
    assert h.state['claims'][c2]['premises'][c1]['version'] == 2
    assert not h.state['invalid']


def test_bad_delta_does_not_partially_write(h):
    oid = source(h); c1 = add(h)
    before = h.state['claims']
    result = send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'Changed', 'refs': [oid]},
                                                {'claim': 'c99', 'finding': 'Bad', 'refs': [oid]}]}))[0]
    assert not result['ok'] and h.state['claims'] == before


def test_cycle_through_existing_claim_rejected(h):
    source(h); c1 = add(h); c2 = add(h, 'Derived', refs=[c1])
    result = send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'cycle', 'refs': [c2]}]}))[0]
    assert not result['ok'] and result['code'] == 'dependency_cycle'
    assert h.state['claims'][c1]['version'] == 1


def test_noop_and_aba_versions(h):
    oid = source(h); c1 = add(h)
    same = send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'A fact', 'refs': [oid]}]}))[0]
    assert same['changes']['noop'] and h.state['claims'][c1]['version'] == 1
    send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'B', 'refs': [oid]}]}))
    send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'A fact', 'refs': [oid]}]}))
    assert h.state['claims'][c1]['meaning_version'] == 3


def test_retired_id_not_reused(h):
    oid = source(h); c1 = add(h)
    send(h, ('update_state', {'retire': [c1]}))
    assert add(h, refs=[oid]) == 'c2'
    assert h.state['claims'][c1]['retired']


def test_own_update_then_submit_uses_new_version(h):
    oid = source(h); c1 = add(h)
    result = send(h, [('update_state', {'revise': [{'claim': c1, 'finding': 'New', 'refs': [oid]}]}),
                      ('submit_answer', {'answer': 'A', 'refs': [c1]})])
    assert result[1]['ok']
    assert result[1]['terminal']['basis']['premises'][c1]['version'] == 2
    assert result[1]['terminal']['basis']['trace'][0]['origin'] == 'own_committed_update'


def test_failed_update_stops_submit(h):
    source(h)
    result = send(h, [('update_state', {'revise': [{'claim': 'c99', 'finding': 'Bad', 'refs': ['this']}]}),
                      ('submit_answer', {'answer': 'A', 'refs': ['this']})])
    assert result[1]['code'] == 'not_executed' and h.terminal is None


def test_no_source_default_not_inherited(h):
    source(h)
    send(h, ('update_state', {'draft': {'answer': 'Old', 'refs': ['this']}}))
    result = send(h, ('submit_answer', {'answer': 'New'}))[0]
    assert result['ok'] and result['terminal']['basis']['sources'] == []


def test_claim_without_raw_path_is_note_not_evidence(h):
    result = send(h, ('update_state', {'add': [{'requirement': 'r', 'finding': 'Guess', 'refs': []}]}))[0]
    assert result['code'] == 'ungrounded_claim'
    assert send(h, ('update_state', {'note': 'Guess to investigate'}))[0]['ok']


def test_history_recovers_old_search_and_note(h):
    source(h)
    send(h, ('update_state', {'note': 'old bridge designer clue'}))
    page = send(h, ('read_evidence', {'query': 'designer'}))[0]
    assert page['ok']
    kinds = {r['kind'] for r in page['history']}
    assert 'search_hit' in kinds and 'model_note_not_evidence' in kinds


def test_window_cursor_immutable_snapshot():
    docs = [{'docid': 'A', 'title': 'long', 'content': 'long ' + 'abcdef' * 100}]
    r = MemoryRetriever(docs)
    h = Harness('Q', r, config=Config(observation_chars=40, paragraph_chars=10))
    first = source(h, 'long')
    cursor = next(iter(h.state['cursors']))
    r.documents['A']['content'] = 'CHANGED'
    second = send(h, ('open_page', {'cursor': cursor}))[0]['observation']
    assert second['text'] == docs[0]['content'][40:80]
    assert h.state['observations'][first]['text'] == docs[0]['content'][:40]
    h.close()


def test_multi_tool_native_receipts_all_paired(h):
    decision = h.begin()
    message = {'role': 'assistant', 'tool_calls': [
        {'id': str(i), 'type': 'function', 'function': {'name': 'search', 'arguments': canonical({'query': 'tournament'})}} for i in range(6)]}
    rows = h.respond(decision, message)
    assert len(rows) == 6 and all(r['code'] == 'not_executed' for r in rows)
    group = h.state['history'][-1]['messages']
    assert len([m for m in group if m['role'] == 'tool']) == 6


def test_duplicate_native_call_ids_no_execution(h):
    d = h.begin()
    call = {'id': 'same', 'type': 'function', 'function': {'name': 'search', 'arguments': '{"query":"x"}'}}
    rows = h.respond(d, {'role': 'assistant', 'tool_calls': [call, call]})
    assert rows[0]['code'] == 'policy_protocol_error' and h.state['backend_calls'] == 0


def test_decision_one_use(h):
    d = h.begin()
    msg = {'role': 'assistant', 'tool_calls': [{'id': 't', 'type': 'function', 'function': {'name': 'search', 'arguments': '{"query":"x"}'}}]}
    h.respond(d, msg)
    with pytest.raises(ContractError):
        h.respond(d, msg)


def test_state_property_does_not_allow_mutation(h):
    s = h.state
    s['exposed'].append('o99')
    assert h.state['exposed'] == []
