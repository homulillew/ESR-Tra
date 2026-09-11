import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from esr_harness.client import UsageBudget
from esr_harness.context import visible_ids
from esr_harness.engine import Harness
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config, HarnessError
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from esr_harness.runner import messages_for, replay, run
from esr_harness.tool_turn import NativeTurn, execute_turn, recover_incomplete, result_blocks
from .helpers import env, opened, update
from .test_strong_api_recovery import Transport


def turn(h, *calls):
    return NativeTurn('fixture-request', [{'type':'tool_use', 'id':f'call{i}', 'name':name, 'input':args}
                                        for i, (name, args) in enumerate(calls)], h.available_tools())


def native_env(**kwargs):
    return env(config=Config(max_tool_calls=4, **kwargs))


def receipts(h, tid='d1'):
    return list(h.native_turns[tid]['results'].values())


def test_independent_searches_one_decision_distinct_results():
    h = native_env()
    t = turn(h, ('search', {'query':'Mira'}), ('search', {'query':'Taylor'}))
    execute_turn(h, t, 'd1')
    assert len(h.actions) == 2 and all(r['ok'] for r in receipts(h))
    assert [c['id'] for c in t.calls] == [r['tool_use_id'] for r in result_blocks(h.native_turns['d1'])]
    assert h.native_turns['d1']['complete']


@pytest.mark.parametrize('mode', ['baseline', 'esr'])
def test_two_reread_bodies_reach_actual_native_request(mode, tmp_path):
    h = native_env(mode=mode, audit_mode='off')
    o1, o2 = opened(h), opened(h, 'd2')
    if mode == 'esr':
        update(h, o1, claim_updates=[{'claim_id':'c0','finding':'Two sources','observation_ids':[o1,o2]}])
    execute_turn(h, turn(h, ('read_evidence', {'observation_id':o1}), ('read_evidence', {'observation_id':o2})), 'd1')
    assert set(visible_ids(h)) == {o1, o2}
    c = AnthropicClient(Transport([]), UsageBudget(), h.ledger, GlobalBudget(tmp_path/'budget.sqlite'), config=RemoteConfig(max_tool_calls=4))
    body = c.body(messages_for(h, c), 32)
    blocks = [b for m in body['messages'] if isinstance(m['content'], list) for b in m['content'] if b['type']=='tool_result']
    returned = [json.loads(b['content'])['observation'] for b in blocks]
    assert [v['observation_id'] for v in returned] == [o1,o2]
    assert [v['text'] for v in returned] == [h.observations[o]['text'] for o in [o1,o2]]
    assert 'admission_reservation' not in json.dumps(body)
    h.record_exposure([o1,o2], 'd2', 'unknown', native_turn_ids=['d1'])
    assert not h.native_turns['d1']['delivered']
    h.record_exposure([o1,o2], 'd3', native_turn_ids=['d1'])
    assert h.native_turns['d1']['delivered']


def test_mixed_valid_invalid_has_two_receipts_and_preserves_good_result():
    h = native_env()
    execute_turn(h, turn(h, ('search', {'query':'Mira'}), ('search', {'bogus':'bad'})), 'd1')
    assert len(h.actions) == 1
    assert receipts(h)[0]['ok'] and receipts(h)[1]['execution'] == 'not_executed'


@pytest.mark.parametrize('case', ['over_limit','mixed_write','forward_open','forward_read','focus'])
def test_rejected_groups_never_silently_execute_prefix(case):
    h = native_env()
    calls = [('search', {'query':'Lake'})]*5 if case=='over_limit' else {
        'mixed_write':[('update_state', {'answer':'x'}), ('search', {'query':'Lake'})],
        'forward_open':[('search', {'query':'Lake'}), ('open_page', {'docid':'d1'})],
        'forward_read':[('read_evidence', {'observation_id':'o99'}), ('read_evidence', {'observation_id':'o98'})],
        'focus':[('search', {'query':'Lake','focus':{'claim_id':'c0','need':'one'}}), ('search', {'query':'Lake','focus':{'claim_id':'c0','need':'two'}})],
    }.get(case)
    execute_turn(h, turn(h, *calls), 'd1')
    assert len(receipts(h)) == len(calls)
    if case == 'forward_open':
        assert receipts(h)[0]['ok'] and not receipts(h)[1]['ok'] and not h.documents
    else:
        assert all(not r['ok'] for r in receipts(h)) and not h.actions


@pytest.mark.parametrize('ids', [['same','same'], ['', 'ok'], [None,'ok']])
def test_invalid_call_ids_keep_proposal_and_execute_nothing(ids):
    h = native_env()
    t = turn(h, ('search', {'query':'Lake'}), ('search', {'query':'Other'}))
    for c, cid in zip(t.content, ids):
        c['id'] = cid
    with pytest.raises(HarnessError) as exc:
        execute_turn(h, t, 'd1')
    assert len(exc.value.proposal['native_tool_calls']) == 2 and not h.actions


@pytest.mark.parametrize('field,value', [('name', []), ('input', None), ('input', [])])
def test_malformed_native_envelope_cannot_poison_next_provider_request(field,value):
    h = native_env()
    t = turn(h, ('search', {'query':'Lake'}), ('search', {'query':'Other'}))
    t.content[1][field] = value
    with pytest.raises(HarnessError) as exc:
        execute_turn(h, t, 'd1')
    assert len(exc.value.proposal['call_results']) == 2
    assert not h.native_turns and not h.actions


def test_search_parent_resolved_at_group_entry():
    h = native_env()
    first = h.execute('search', {'query':'Lake'})['action_id']
    execute_turn(h, turn(h, ('search', {'query':'Lake'}), ('open_page', {'docid':'d1'})), 'd1')
    assert receipts(h)[1]['retrieval_parent'] == first
    assert h.native_turns['d1']['calls'][1]['input'] == {'docid':'d1'}


def test_action_slots_and_group_capacity_reserved_before_backend():
    for limit, admission in [(1, None), (64, lambda h: False)]:
        h = native_env(max_actions=limit)
        h.admission = admission
        execute_turn(h, turn(h, ('search', {'query':'Lake'}), ('search', {'query':'Other'})), 'd1')
        assert len(receipts(h)) == 2 and not h.actions and not h.searches


def test_cumulative_admission_keeps_first_result_when_second_does_not_fit():
    h = native_env()
    h.admission = lambda p: len(p.searches) < 2
    execute_turn(h, turn(h, ('search', {'query':'Lake'}), ('search', {'query':'Other'})), 'd1')
    assert receipts(h)[0]['ok'] and receipts(h)[1]['error_code']=='context_capacity'
    assert 'unadmitted_output' in h.actions[-1]
    assert len(h.searches)==1


def test_uncertain_failure_keeps_receipt_and_skips_rest():
    h = native_env()
    def fail(*a):
        raise TimeoutError('private details must not be logged')
    h.retriever.search = fail
    execute_turn(h, turn(h, ('search', {'query':'Lake'}), ('search', {'query':'Other'})), 'd1')
    assert receipts(h)[0]['execution']=='unknown' and receipts(h)[1]['execution']=='not_executed'
    assert 'private details' not in json.dumps(h.ledger.events())


def test_restart_does_not_reexecute_committed_or_uncertain_calls(tmp_path):
    h = env(config=Config(max_tool_calls=4), ledger=Ledger(tmp_path/'episode.sqlite'))
    execute_turn(h, turn(h, ('search', {'query':'Lake'})), 'd1')
    t = turn(h, ('search', {'query':'Other'}), ('search', {'query':'Taylor'}))
    h._commit({'type':'native_turn','decision_id':'d2','request_id':'interrupted','content':t.content,'calls':t.calls,'sequence':len(h.ledger.events())})
    h._commit({'type':'native_call_started','decision_id':'d2','index':0})
    h.ledger.close()
    h = env(config=Config(max_tool_calls=4), ledger=Ledger(tmp_path/'episode.sqlite'))
    h.retriever.search = lambda *a: pytest.fail('must not retry on recovery')
    recover_incomplete(h)
    assert len(h.actions)==1 and h.terminal['outcome']=='service_error'
    assert receipts(h,'d2')[0]['execution']=='unknown' and receipts(h,'d2')[1]['execution']=='not_executed'
    h.ledger.close()
    restored = replay(tmp_path/'episode.sqlite')
    assert restored.native_turns['d2']['complete'] and len(restored.actions)==1
    restored.ledger.close()


def test_native_roundtrip_and_actual_usage_no_extra_policy_call(tmp_path):
    h = native_env(mode='baseline', audit_mode='off')
    def response(calls):
        return {'model':'fixture','stop_reason':'tool_use','content':calls,'usage':{'input_tokens':20,'output_tokens':10}}
    first = turn(h, ('search', {'query':'Mira'}), ('search', {'query':'Taylor'})).content
    last = [{'type':'tool_use','id':'finish1','name':'finish','input':{'answer':'Taylor'}}]
    transport = Transport([response(first), response(last)])
    c = AnthropicClient(transport, UsageBudget(), h.ledger, GlobalBudget(tmp_path/'budget.sqlite'),
                        config=RemoteConfig(max_tool_calls=4, max_requests=2, transport_attempts=1))
    result = run(h,c)
    assert result['terminal']['outcome']=='submitted' and c.request_status()['used']==2
    assert result['native_tools']['proposed_calls']==3 and result['attempts']==3
    assert c.budget.completion_tokens==20
    native = [m for m in transport.requests[1]['messages'] if isinstance(m['content'],list)]
    assert [b['tool_use_id'] for m in native for b in m['content'] if b['type']=='tool_result']==['call0','call1']


def test_error_stop_counts_decisions_but_reports_each_failed_call(tmp_path):
    h = native_env(max_execution_errors=2)
    class Policy:
        fits = staticmethod(lambda _: True)
        def complete(self, *a, **kw):
            return turn(h, ('update_state', {'answer':'x'}), ('search', {'query':'Lake'}))
    result = run(h, Policy())
    assert result['terminal']['outcome']=='execution_error_limit'
    assert result['native_tools']['failed_calls']==4 and result['native_tools']['error_decisions']==2


def test_current_readiness_matches_offered_audit():
    h = native_env()
    assert not h.readiness()['verify_answer']['ready']
    assert 'verify_answer' not in {t['name'] for t in h.available_tools()}


def test_completed_decision_cannot_be_executed_again():
    h = native_env()
    t = turn(h, ('search', {'query':'Lake'}))
    execute_turn(h, t, 'd1')
    with pytest.raises(ValueError, match='already journaled'):
        execute_turn(h, t, 'd1')
    assert len(h.actions)==1


def test_uncommitted_provider_decision_stops_before_resampling():
    h = native_env()
    h.ledger.append({'type':'decision','decision_id':'d1'})
    h.ledger.append({'type':'generation_request','request_id':'unknown','purpose':'policy','reserved_completion_tokens':12})
    class NoCall:
        def complete(self, *a, **kw):
            pytest.fail('must not regenerate interrupted decision')
    result = run(h, NoCall())
    assert result['terminal']['outcome']=='service_error'
    assert UsageBudget(100,h.ledger.events()).charged_tokens==12


def test_native_baseline_instruction_does_not_request_esr_state():
    h = native_env(mode='baseline', audit_mode='off')
    instructions = messages_for(h, SimpleNamespace(fits=lambda _: True))[0]['content'].split('\nTools:\n')[0]
    assert 'focus' not in instructions and 'State updates' not in instructions and 'Audit' not in instructions


def test_new_reads_respect_pending_limit_for_whole_execution():
    h = native_env(max_pending_views=1)
    h.execute('search', {'query':'Lake'})
    execute_turn(h, turn(h, ('open_page', {'docid':'d1'}), ('open_page', {'docid':'d2'})), 'd1')
    assert all(r['error_code']=='context_capacity' for r in receipts(h))
    assert not h.pending and not h.documents and len(h.actions)==1


def test_reread_reservation_checks_all_bodies_together():
    h = native_env()
    o1, o2 = opened(h), opened(h, 'd2')
    update(h, o1, claim_updates=[{'claim_id':'c0','finding':'Both sources','observation_ids':[o1,o2]}])
    class Capacity:
        @staticmethod
        def fits(messages):
            raw = json.dumps(messages)
            return not ('Mira won' in raw and 'Taylor won' in raw)
    h.admission = lambda p: Capacity.fits(messages_for(p, SimpleNamespace(fits=lambda _: True)))
    execute_turn(h, turn(h, ('read_evidence', {'observation_id':o1}), ('read_evidence', {'observation_id':o2})), 'd1')
    assert receipts(h)[0]['ok'] and not receipts(h)[1]['ok']
    assert 'unadmitted_output' in h.actions[-1]
