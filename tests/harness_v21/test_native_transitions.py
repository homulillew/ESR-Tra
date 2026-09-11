"""Offline integration regressions through the real adapter and decision loop."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from esr_harness.client import UsageBudget
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from esr_harness.runner import messages_for, replay, run
from esr_harness.tool_turn import execute_turn, result_blocks
from .helpers import env, opened
from .test_native_tool_turns import native_env, receipts, turn
from .test_strong_api_recovery import Transport

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from audit_native_tool_turns import audit, visible_texts


FOCUS = {'claim_id': 'c0', 'need': 'Check the earlier winner'}


def response(name, args, index, native):
    content = ([{'type': 'tool_use', 'id': f'call-{index}', 'name': name, 'input': args}]
               if native else [{'type': 'text', 'text': json.dumps({'action': name, 'arguments': args})}])
    return {'model': 'fixture', 'stop_reason': 'tool_use' if native else 'end_turn',
            'content': content, 'usage': {'input_tokens': 20, 'output_tokens': 10}}


def history_actions(body):
    result = []
    for message in body['messages']:
        if message['role'] != 'assistant':
            continue
        content = message['content']
        if isinstance(content, str):
            result.append(json.loads(content)['action'])
        else:
            for block in content:
                result.append(block['name'] if block['type'] == 'tool_use'
                              else json.loads(block['text'])['action'])
    return result


@pytest.mark.parametrize('first_native', [True, False])
@pytest.mark.parametrize('mode', ['baseline', 'esr'])
def test_repeated_native_text_switch_preserves_history_and_delivery(tmp_path, first_native, mode):
    h = env(config=Config(max_tool_calls=4, mode=mode, audit_mode='off'),
            ledger=Ledger(tmp_path/'ledger.sqlite'))
    actions = [('search', {'query': 'Lake'}), ('open_page', {'docid': 'd2'}),
               ('read_evidence', {'observation_id': 'o1'}), ('search', {'query': 'Taylor'})]
    if mode == 'esr':
        actions += [('update_state', {'answer': 'Taylor', 'claim_updates': [
            {'claim_id': 'c0', 'finding': 'Taylor won in 2008.', 'observation_ids': ['o1']}]}),
                    ('submit_answer', {})]
    else:
        actions += [('finish', {'answer': 'Taylor'})]
    transport = Transport([response(name, args, i, (i % 2 == 0) == first_native)
                           for i, (name, args) in enumerate(actions)])
    client = AnthropicClient(transport, UsageBudget(), h.ledger, GlobalBudget(tmp_path/'budget.sqlite'),
                            config=RemoteConfig(max_tool_calls=4, max_requests=len(actions), transport_attempts=1))
    result = run(h, client)
    assert result['terminal']['outcome'] == 'submitted'
    assert len(transport.requests) == len(actions) == h.attempts
    assert all(a['result']['ok'] for a in h.actions)
    for i, body in enumerate(transport.requests):
        assert 'admission_reservation' not in json.dumps(body)
        if mode == 'baseline':
            assert history_actions(body) == [name for name, _ in actions[:i]]
        if i in {2, 3}:
            assert h.observations['o1']['text'] in visible_texts(body['messages'])['o1']
        pending = []
        for message in body['messages']:
            blocks = message['content'] if isinstance(message['content'], list) else []
            results = [b['tool_use_id'] for b in blocks if b['type'] == 'tool_result']
            assert results == pending
            pending = [b['id'] for b in blocks if b['type'] == 'tool_use']
        assert not pending
    original = deepcopy(h.actions)
    h.ledger.close()
    assert audit(tmp_path)['problems'] == []
    restored = replay(tmp_path/'ledger.sqlite')
    assert restored.actions == original and restored.terminal == result['terminal']
    if mode == 'baseline':
        assert history_actions(client.body(messages_for(restored, SimpleNamespace(fits=lambda _: True)), 32)) == [name for name, _ in actions]
    restored.ledger.close()


@pytest.mark.parametrize('tool,args', [('search', {'query': 'Taylor'}), ('open_page', {'docid': 'd2'}),
                                      ('read_evidence', {'observation_id': 'o1'})])
@pytest.mark.parametrize('failure', ['runtime', 'schema', 'invalid_focus'])
def test_uncommitted_focus_blocks_dependent_calls_without_backend_io(monkeypatch, tool, args, failure):
    h = native_env(audit_mode='off')
    opened(h)
    first = {'query': 'Lake', 'focus': deepcopy(FOCUS)}
    if failure == 'runtime':
        first['anchor_refs'] = ['o999']
    elif failure == 'schema':
        first['bogus'] = 'invalid argument'
    else:
        first['focus']['claim_id'] = 'c99'
    before = deepcopy(h.state)
    prior_actions = len(h.actions)
    monkeypatch.setattr(h.retriever, 'search', lambda *a: pytest.fail('rejected search reached backend'))
    monkeypatch.setattr(h.retriever, 'get_document', lambda *a: pytest.fail('rejected open reached backend'))
    execute_turn(h, turn(h, ('search', first), (tool, args)), 'd1')
    assert not receipts(h)[0]['ok']
    assert receipts(h)[1]['error_code'] == 'dependency_failed'
    assert receipts(h)[1]['execution'] == 'not_executed'
    assert h.state == before
    assert len(h.actions) == prior_actions + (failure == 'runtime')
    assert h.native_turns['d1']['started'] == ([0] if failure == 'runtime' else [])
    assert [b['tool_use_id'] for b in result_blocks(h.native_turns['d1'])] == ['call0', 'call1']


@pytest.mark.parametrize('tool,args', [('search', {'query': 'Taylor'}), ('open_page', {'docid': 'd2'}),
                                      ('read_evidence', {'observation_id': 'o1'})])
def test_committed_focus_allows_dependent_call(tool, args):
    h = native_env(audit_mode='off')
    opened(h)
    execute_turn(h, turn(h, ('search', {'query': 'Lake', 'focus': FOCUS}), (tool, args)), 'd1')
    assert all(r['ok'] for r in receipts(h))
    assert receipts(h)[1]['purpose']['need'] == FOCUS['need']


@pytest.mark.parametrize('explicit_second', [False, True])
def test_failure_preserves_independent_search(explicit_second):
    h = native_env()
    focus = FOCUS if explicit_second else h.state['focus']
    second = {'query': 'Taylor', **({'focus': focus} if explicit_second else {})}
    execute_turn(h, turn(h, ('search', {'query': 'Lake', 'focus': focus, 'anchor_refs': ['o999']}),
                         ('search', second)), 'd1')
    assert not receipts(h)[0]['ok'] and receipts(h)[1]['ok']
    assert receipts(h)[1]['purpose']['need'] == focus['need']


def test_failed_focus_does_not_block_independent_directory():
    h = native_env()
    oid = opened(h)
    execute_turn(h, turn(h, ('search', {'query': 'Lake', 'focus': FOCUS, 'anchor_refs': ['o999']}),
                         ('read_evidence', {'directory_cursor': 'start'})), 'd1')
    assert not receipts(h)[0]['ok'] and receipts(h)[1]['ok']
    assert receipts(h)[1]['directory'][0]['observation_id'] == oid


def test_normalized_focus_and_original_arguments_are_both_preserved():
    h = native_env()
    args = {'query': 'Lake', 'focus': {**FOCUS, 'need': '  '+FOCUS['need']+'  '}}
    proposal = turn(h, ('search', args), ('search', {'query': 'Taylor', 'focus': FOCUS}))
    original = deepcopy(proposal.content)
    execute_turn(h, proposal, 'd1')
    assert all(r['ok'] for r in receipts(h))
    assert h.state['focus'] == FOCUS
    assert h.native_turns['d1']['content'] == original


def test_text_preview_capacity_rejection_keeps_committed_native_history():
    h = native_env(mode='baseline', audit_mode='off')
    execute_turn(h, turn(h, ('search', {'query': 'Lake'})), 'd1')
    prior = deepcopy(h.ledger.events())
    seen = []
    class Capacity:
        fits = staticmethod(lambda _: True)
    def admit(preview):
        seen.append(messages_for(preview, Capacity()))
        assert h.ledger.events() == prior
        return False
    h.admission = admit
    result = h.execute('search', {'query': 'Taylor'}, decision_id='d2')
    assert result['error_code'] == 'context_capacity'
    assert len(seen) == 1 and len(h.searches) == 1
    assert h.actions[-1]['unadmitted_output']['ok']
    assert h.actions[-1]['delta'] == {}
    assert h.ledger.events()[:-1] == prior


def test_committed_focus_survives_retrieval_error_and_allows_next_search(monkeypatch):
    h = native_env()
    search = h.retriever.search
    queries = []
    def fail_first(query, top_k):
        queries.append(query)
        return 'malformed retrieval result' if len(queries) == 1 else search(query, top_k)
    monkeypatch.setattr(h.retriever, 'search', fail_first)
    execute_turn(h, turn(h, ('search', {'query': 'Lake', 'focus': FOCUS}),
                         ('search', {'query': 'Taylor'})), 'd1')
    assert receipts(h)[0]['error_code'] == 'retrieval_error'
    assert receipts(h)[0]['focus_edit_applied']
    assert receipts(h)[1]['ok'] and receipts(h)[1]['purpose']['need'] == FOCUS['need']
    assert queries == ['Lake', 'Taylor']


def test_dependency_error_reaches_policy_and_next_decision_recovers(tmp_path):
    h = env(config=Config(max_tool_calls=4, audit_mode='off'), ledger=Ledger(tmp_path/'ledger.sqlite'))
    failed = response('search', {'query': 'Lake', 'focus': FOCUS, 'anchor_refs': ['o999']}, 0, True)
    failed['content'] += response('search', {'query': 'Taylor'}, 1, True)['content']
    responses = [failed, response('search', {'query': 'Taylor', 'focus': FOCUS}, 2, True),
                 response('open_page', {'docid': 'd2'}, 3, False),
                 response('update_state', {'answer': 'Taylor', 'claim_updates': [
                     {'claim_id': 'c0', 'finding': 'Taylor won in 2008.', 'observation_ids': ['o1']}]}, 4, True),
                 response('submit_answer', {}, 5, False)]
    transport = Transport(responses)
    budget = GlobalBudget(tmp_path/'budget.sqlite')
    client = AnthropicClient(transport, UsageBudget(), h.ledger, budget,
                            config=RemoteConfig(max_tool_calls=4, max_requests=5, transport_attempts=1))
    result = run(h, client)
    assert result['terminal']['outcome'] == 'submitted'
    assert result['invalid_actions'] == 2 and result['invalid_executed_actions'] == 1
    assert result['native_tools']['not_executed'] == 1
    assert h.attempts == len(transport.requests) == budget.request_status()['used'] == 5
    errors = [json.loads(b['content']) for m in transport.requests[1]['messages']
              if isinstance(m['content'], list) for b in m['content'] if b['type'] == 'tool_result']
    assert [r['error_code'] for r in errors] == ['unexposed_reference', 'dependency_failed']
    first = next(iter(h.native_turns.values()))
    assert first['content'] == failed['content'] and first['delivered']
    h.ledger.close()
    assert audit(tmp_path)['problems'] == []
    restored = replay(tmp_path/'ledger.sqlite')
    assert next(iter(restored.native_turns.values()))['focus_requirements'] == first['focus_requirements']
    assert restored.state['focus'] == FOCUS
    restored.ledger.close()


def test_delivery_inspector_decodes_merged_text_without_accepting_missing_body():
    view = {'observation': {'observation_id': 'o1', 'text': 'First line\nSecond line'}}
    merged = json.dumps(view) + '\n\n' + json.dumps({'remaining_actions': 10})
    assert visible_texts(merged) == {'o1': {'First line\nSecond line'}}
    assert visible_texts(json.dumps({'observation': {'observation_id': 'o1'}})) == {}
