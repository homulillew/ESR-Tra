from copy import deepcopy
import pytest
from esr_harness_v3.protocol import ContractError, Config, SCHEMAS, parse_json, tools, validate_action


@pytest.mark.parametrize('name,args', [
    ('search', {'query': 'x'}), ('open_page', {'ref': 'd1'}), ('open_page', {'cursor': 'k1'}),
    ('read_evidence', {'query': 'old hint'}), ('read_evidence', {'ref': 'c1'}),
    ('read_evidence', {'ref': 'o1:p2'}), ('read_evidence', {'cursor': 'k1'}),
    ('update_state', {'add': [{'requirement': 'year', 'finding': '2014', 'refs': ['this']}]}),
    ('update_state', {'revise': [{'claim': 'c1', 'finding': '2015', 'refs': ['o2']}]}),
    ('update_state', {'revise': [{'claim': 'c1', 'requirement': 'changed'}]}),
    ('update_state', {'draft': None}), ('update_state', {'note': ''}),
    ('update_state', {'retire': ['c1']}), ('verify_answer', {}),
    ('verify_answer', {'answer': 'A', 'refs': []}), ('submit_answer', {'answer': 'A'}),
    ('submit_answer', {'decision': 'abstain', 'reason': 'No answer'}),
])
def test_valid(name, args):
    validate_action(name, args)


@pytest.mark.parametrize('name,args', [
    ('search', {'query': ' '}), ('search', {'query': 'x', 'top_k': True}),
    ('search', {'query': 'x', 'top_k': 21}), ('open_page', {'ref': 'o1'}),
    ('open_page', {'ref': 'd1', 'cursor': 'k1'}), ('open_page', {'cursor': 'k1', 'query': 'x'}),
    ('read_evidence', {'ref': 'this'}), ('read_evidence', {'ref': 'o1', 'query': 'x'}),
    ('read_evidence', {}), ('update_state', {}),
    ('update_state', {'add': [{'claim': 'c1', 'requirement': 'r', 'finding': 'f', 'refs': ['o1']}]}),
    ('update_state', {'add': [{'claim_id': 'c1', 'requirement': 'r', 'finding': 'f', 'refs': ['o1']}]}),
    ('update_state', {'revise': [{'claim': 'o1', 'finding': 'f', 'refs': ['o1']}]}),
    ('update_state', {'revise': [{'claim': 'c1', 'finding': 'f'}]}),
    ('update_state', {'claim_updates': []}), ('update_state', {'focus': {'claim_id': 'c1'}}),
    ('verify_answer', {'answer': 'A'}), ('verify_answer', {'refs': []}),
    ('submit_answer', {'answer': ' '}), ('submit_answer', {'answer': 'A', 'refs': ['d1']}),
    ('submit_answer', {'answer': 'A', 'refs': ['o1', 'o1']}),
    ('submit_answer', {'answer': 'A', 'decision': 'abstain', 'reason': 'x'}),
])
def test_invalid(name, args):
    with pytest.raises(ContractError):
        validate_action(name, args)


def test_no_shared_schema_aliases():
    before = deepcopy(SCHEMAS)
    first = tools()
    first[0]['function']['parameters']['properties']['query']['enum'] = ['bad']
    assert SCHEMAS == before
    assert 'enum' not in tools()[0]['function']['parameters']['properties']['query']


@pytest.mark.parametrize('value', ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{broken'])
def test_strict_json(value):
    with pytest.raises(ContractError):
        parse_json(value)


@pytest.mark.parametrize('kwargs', [{'max_model_calls': 0}, {'max_actions': True}, {'audit_mode': 'soft'},
                                  {'audit_attempts': 3}, {'context_limit': 10, 'output_reserve': 10}])
def test_bad_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)
