"""Synthetic dependency and evidence boundaries for the ordered-call experiment."""
import json
from copy import deepcopy

import pytest

from esr_harness.client import UsageBudget
from esr_harness.protocol import Config, HarnessError
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from esr_harness.runner import run, replay
from esr_harness.ledger import Ledger
from esr_harness.tool_turn import execute_turn
from .helpers import env, opened, update
from .test_native_tool_turns import turn, receipts
from .test_strong_api_recovery import Transport


def ordered(**kw):
    return env(config=Config(max_tool_calls=4, ordered_tool_calls=True, **kw))


def patch(oid):
    return {'answer':'Taylor','claim_updates':[{'claim_id':'c0','finding':'Observed winner', 'observation_ids':[oid]}]}


@pytest.mark.parametrize('audit_mode', ['off','soft','hard'])
def test_explicit_update_verify_submit_commits_in_order(audit_mode):
    h=ordered(audit_mode=audit_mode)
    oid=opened(h,'d2')
    calls=[('update_state',patch(oid))]
    if audit_mode!='off':calls.append(('verify_answer',{}))
    calls.append(('submit_answer',{'decision':'answer'}))
    assert 'answer' in next(t for t in h.available_tools() if t['name']=='submit_answer')['parameters']['properties']['decision']['enum']
    execute_turn(h,turn(h,*calls),'d1')
    assert h.terminal['outcome']=='submitted' and h.terminal['answer']=='Taylor'
    assert all(r['ok'] for r in receipts(h)) and len(receipts(h))==len(calls)
    assert len(h.auditor.inputs)==(audit_mode!='off')


@pytest.mark.parametrize('invalid', ['schema','unknown_evidence','audit','hard_unknown'])
def test_failed_prerequisite_cannot_submit_old_answer(invalid):
    mode='hard' if invalid=='hard_unknown' else 'soft' if invalid=='audit' else 'off'
    h=ordered(audit_mode=mode)
    oid=opened(h,'d2');assert update(h,oid)['ok']
    args=patch(oid)
    if invalid=='schema':args['answer']=42
    if invalid=='unknown_evidence':args['claim_updates'][0]['observation_ids']=['o999']
    calls=[('update_state',args)]
    if invalid=='audit':
        h.auditor.value=HarnessError('audit_protocol_error','Synthetic malformed report')
        calls.append(('verify_answer',{}))
    if invalid=='hard_unknown':
        h.auditor.value='unknown'
        calls.append(('verify_answer',{}))
    calls.append(('submit_answer',{'decision':'answer'}))
    execute_turn(h,turn(h,*calls),'d1')
    assert h.terminal is None
    assert receipts(h)[-1]['error_code']==('not_supported' if invalid=='hard_unknown' else 'dependency_failed')
    assert h.state['answer']=='Taylor'


def test_ordered_focus_is_attributed_to_each_committed_search():
    h=ordered(audit_mode='off')
    execute_turn(h,turn(h,
        ('search',{'query':'Lake','focus':{'claim_id':'c0','need':'first relation'}}),
        ('search',{'query':'Other','focus':{'claim_id':'c0','need':'second relation'}})), 'd1')
    assert all(r['ok'] for r in receipts(h))
    purposes=[s['purpose'] for s in h.searches.values()]
    assert purposes[0]['need']=='first relation' and purposes[1]['need']=='second relation'


def test_search_after_update_uses_new_committed_focus():
    h=ordered(audit_mode='off')
    execute_turn(h,turn(h,('update_state',{'focus':{'claim_id':'c0','need':'new bridge'}}),('search',{'query':'Lake'})),'d1')
    assert all(r['ok'] for r in receipts(h))
    assert next(iter(h.searches.values()))['purpose']['need']=='new bridge'


def test_new_body_in_same_turn_cannot_be_cited_or_submitted():
    h=ordered(audit_mode='off')
    h.execute('search',{'query':'Lake'})
    execute_turn(h,turn(h,('open_page',{'docid':'d2'}),('update_state',patch('o1')),
                        ('submit_answer',{'decision':'answer'})),'d1')
    assert receipts(h)[0]['ok']
    assert receipts(h)[1]['error_code']=='unexposed_reference'
    assert receipts(h)[2]['error_code']=='dependency_failed'
    assert h.state['answer'] is None and h.pending=={'o1'} and not h.exposed


def test_forward_search_hit_is_not_guessed():
    h=ordered(audit_mode='off')
    h.execute('search',{'query':'Lake'})
    execute_turn(h,turn(h,('search',{'query':'Other'}),('open_page',{'docid':'d3'})),'d1')
    assert receipts(h)[0]['ok'] and receipts(h)[1]['error_code']=='unexposed_reference'
    assert not h.documents


def test_ending_before_last_is_rejected_without_side_effects():
    h=ordered(mode='baseline',audit_mode='off')
    execute_turn(h,turn(h,('finish',{'answer':'Taylor'}),('search',{'query':'Lake'})),'d1')
    assert not h.actions and h.terminal is None and len(receipts(h))==2


def test_last_policy_request_can_explicitly_update_and_submit(tmp_path):
    h=env(config=Config(max_tool_calls=4,ordered_tool_calls=True,audit_mode='off'),ledger=Ledger(tmp_path/'episode.sqlite'))
    oid=opened(h,'d2')
    response={'model':'fixture','stop_reason':'tool_use',
              'content':turn(h,('update_state',patch(oid)),('submit_answer',{'decision':'answer'})).content,
              'usage':{'input_tokens':40,'output_tokens':20}}
    t=Transport([response])
    client=AnthropicClient(t,UsageBudget(),h.ledger,GlobalBudget(tmp_path/'budget.sqlite'),
                          config=RemoteConfig(max_tool_calls=4,max_requests=1,transport_attempts=1))
    result=run(h,client)
    assert result['terminal']['outcome']=='submitted' and len(t.requests)==1
    assert result['native_tools']['proposed_calls']==2 and result['attempts']==4
    state=deepcopy(h.state);h.ledger.close()
    restored=replay(tmp_path/'episode.sqlite')
    assert restored.state==state and restored.terminal['answer']=='Taylor'
    assert all(t['complete'] for t in restored.native_turns.values())
    restored.ledger.close()


def test_ordered_config_remains_optional_for_old_ledger_headers():
    assert 'ordered_tool_calls' not in Config().to_dict()
    assert Config(ordered_tool_calls=True).to_dict()['ordered_tool_calls'] is True
    with pytest.raises(ValueError):Config(ordered_tool_calls=1)
