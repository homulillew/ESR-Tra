import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import strong_api
from evaluate_strong_api import evaluate
from .test_strong_api_recovery import Transport, response


def test_probe_uses_configured_route_in_actual_provider_request(tmp_path,monkeypatch):
    settings=yaml.safe_load((strong_api.ROOT/'configs/strong_api_forward.yaml').read_text(encoding='utf-8'))
    settings['provider']['model']='fixture-alternate-model'
    config=tmp_path/'config.yaml';config.write_text(yaml.safe_dump(settings),encoding='utf-8')
    transport=Transport([response()]);transport.model='fixture-alternate-model'
    monkeypatch.setattr(strong_api,'LanzClient',lambda **kwargs:transport)
    monkeypatch.setattr(strong_api,'snapshot',lambda:{'fixture':True})
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN','SYNTHETIC_TEST_SECRET')
    monkeypatch.setattr(sys,'argv',['strong_api.py','probe','--native','--root',str(tmp_path),'--config',str(config)])
    strong_api.main()
    assert len(transport.requests)==1
    assert transport.requests[0]['model']=='fixture-alternate-model'
    exported=next(tmp_path.glob('probe_*/provider_requests.jsonl')).read_text(encoding='utf-8')
    assert 'fixture-alternate-model' in exported and 'SYNTHETIC_TEST_SECRET' not in exported


def test_judge_uses_rollout_model_and_prevents_silent_route_change(tmp_path):
    directory=tmp_path/'run';directory.mkdir()
    (directory/'summary.json').write_text(json.dumps({'terminal':{'outcome':'submitted','answer':'synthetic answer'}}),encoding='utf-8')
    (directory/'manifest.json').write_text(json.dumps({'category':'development','qid':'fixture',
        'provider':{'config':{'model':'fixture-alternate-model'}}}),encoding='utf-8')
    reply=response();reply['content'][0]['text']='correct: yes'
    transport=Transport([reply]);transport.model='wrong-route'
    budget=strong_api.GlobalBudget(tmp_path/'budget.sqlite')
    with pytest.raises(ValueError,match='Judge route'):
        evaluate(directory,{},'{question} {response} {correct_answer}',transport,budget)
    assert not transport.requests
    transport.model='fixture-alternate-model'
    grade=evaluate(directory,{'fixture':{'query':'Synthetic question','answer':'synthetic answer'}},
                   '{question} {response} {correct_answer}',transport,budget)
    assert transport.requests[0]['model']=='fixture-alternate-model'
    assert grade['method']=='official_BC+_grader_with_fixture-alternate-model'
