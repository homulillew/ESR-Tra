from copy import deepcopy
import pytest
from stride_search.contract import Config, ContractError, loads, tools, validate

@pytest.mark.parametrize('text', ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1} trailing', '['])
def test_strict_json(text):
    with pytest.raises(ContractError): loads(text)

@pytest.mark.parametrize('config', [dict(max_model_calls=True), dict(max_batch=9), dict(read_chars=6001),
    dict(context_limit=10,response_reserve=10), dict(max_actions=0), dict(notes_enabled=1),
    dict(context_mode='magic'), dict(answer_prefix=1), dict(max_total_output_tokens=1)])
def test_config_rejects(config):
    with pytest.raises(ValueError): Config(**config)

@pytest.mark.parametrize('name,args', [
    ('search',{'queries':['A'],'top_k':True}), ('search',{'queries':['A'],'top_k':1.0}),
    ('search',{'queries':[]}), ('search',{'queries':['A','A']}),
    ('read',{'ref':'d1','start':-1}), ('read',{'ref':'e0'}),
    ('finish',{'answer':'A'}), ('finish',{'answer':'   ','refs':[]}),
    ('finish',{'answer':'A','refs':['d1']}), ('notes',{'op':'put','key':'a','text':'a','anchors':['d1']}),
    ('read',{'ref':'d1','unknown':2}), ('unknown',{})])
def test_invalid_actions(name,args):
    with pytest.raises(ContractError): validate(name,args)

def test_schema_no_alias_pollution():
    first=tools(notes_enabled=True,final=False)
    first[0]['function']['parameters']['properties']['queries']['items']['enum']=['bad']
    assert 'enum' not in tools(notes_enabled=True,final=False)[0]['function']['parameters']['properties']['queries']['items']
    assert [t['function']['name'] for t in tools(notes_enabled=True,final=True)] == ['finish']
    assert 'notes' not in [t['function']['name'] for t in tools(notes_enabled=False,final=False)]
