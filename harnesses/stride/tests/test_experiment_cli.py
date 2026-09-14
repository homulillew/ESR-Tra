from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from stride_search import Config,ContractError
from stride_search.cli import main
from stride_search.contract import canonical,loads
from stride_search.experiment import make_plan,run_plan,summarize,read_cases,checked_plan
from stride_search.fixtures import smoke_model,smoke_corpus,ScriptedModel
from stride_search.providers import ByteCounter
from test_engine import S,R,F,A


def plan(cases=None):
    return make_plan(cases or [{'id':'one','question':'Q'}],Config(max_model_calls=3),
        {'notes_off':{'notes_enabled':False},'notes_on':{}},model_identity=smoke_model().identity,
        retriever_identity=smoke_corpus().identity,counter_identity=ByteCounter.identity,seed=13)

def test_plan_repeatable_and_tamper_evident():
    assert plan()==plan()
    p=plan();p['plan']['cases'][0]['question']='changed'
    with pytest.raises(ContractError):checked_plan(p)

@pytest.mark.parametrize('case',[{'id':'x','question':'Q','answer':'secret'}, {'id':'x','question':'Q','gold_docid':'a'},
    {'id':'x','question':'Q','labels':[]}, {'id':'x'}, {'id':1,'question':'Q'}])
def test_gold_forbidden_at_loader(tmp_path,case):
    p=tmp_path/'cases.jsonl';p.write_text(canonical(case))
    with pytest.raises(ValueError):read_cases(p)

def test_budget_and_source_rules_cannot_differ_across_arms():
    with pytest.raises(ValueError):make_plan([{'id':'x','question':'Q'}],Config(),
        {'a':{},'b':{'require_sources':False}},model_identity={},retriever_identity={},counter_identity={})

def test_complete_queue_unjudged_then_external_judge(tmp_path):
    out=tmp_path/'cohort';result=run_plan(plan(),out,smoke_model,smoke_corpus,ByteCounter,max_total_model_calls=6)
    assert all(r['status']=='submitted' for r in result['rows'])
    assert all(a['formal_accuracy'] is None for a in result['arms'].values())
    labels=[{'slot':r['slot'],'head':r['ledger_head'],'correct':True} for r in result['rows']]
    scored=summarize(out,judgments=labels)
    assert all(a['formal_accuracy']==1 for a in scored['arms'].values())
    labels[0]['head']='wrong'
    with pytest.raises(ContractError):summarize(out,judgments=labels)

def test_insufficient_total_denied_before_output_created(tmp_path):
    out=tmp_path/'cohort'
    with pytest.raises(ValueError):run_plan(plan(),out,smoke_model,smoke_corpus,ByteCounter,max_total_model_calls=5)
    assert not out.exists()

def test_infra_failure_stops_queue_keeps_not_run(tmp_path):
    def fail():return ScriptedModel([ContractError('http_error','429',fatal=True)])
    p=plan([{'id':'a','question':'Q1'},{'id':'b','question':'Q2'}])
    result=run_plan(p,tmp_path/'cohort',fail,smoke_corpus,ByteCounter,max_total_model_calls=12)
    assert [r['status'] for r in result['rows']]==['http_error','NOT_RUN','NOT_RUN','NOT_RUN']
    assert sum(r.get('model_attempts',0) for r in result['rows'])==1
    assert all(a['formal_accuracy'] is None for a in result['arms'].values())

def test_no_rerun_overwrite(tmp_path):
    out=tmp_path/'cohort';run_plan(plan(),out,smoke_model,smoke_corpus,ByteCounter,max_total_model_calls=6)
    with pytest.raises(FileExistsError):run_plan(plan(),out,smoke_model,smoke_corpus,ByteCounter,max_total_model_calls=6)

def test_identity_mismatch_before_requests(tmp_path):
    def wrong():
        m=smoke_model();m.identity={**m.identity,'model':'different'};return m
    out=tmp_path/'cohort';r=run_plan(plan(),out,wrong,smoke_corpus,ByteCounter,max_total_model_calls=6)
    assert all(row['status']=='NOT_RUN' for row in r['rows'])

def test_cli_smoke_replay(tmp_path,capsys):
    out=tmp_path/'smoke'
    assert main(['smoke','--output',str(out)])==0
    assert 'scripted_protocol_smoke_not_BCPlus' in capsys.readouterr().out
    assert main(['replay','--db',str(out/'episode.sqlite')])==0
    assert 'submitted' in capsys.readouterr().out

def test_cli_blocks_network_before_question_read(tmp_path,capsys):
    args=['run','--base-url','http://127.0.0.1:1/v1','--model','x','--model-revision','r',
        '--retrieval-url','http://127.0.0.1:2','--index-id','idx','--counter','utf8_bytes',
        '--question-file',str(tmp_path/'nonexistent'),'--db',str(tmp_path/'no.sqlite'),
        '--max-model-calls','3','--context-limit','100000','--response-reserve','8192']
    assert main(args)==2
    assert '--allow-network' in capsys.readouterr().err
    assert not (tmp_path/'no.sqlite').exists()

def test_cli_requires_explicit_budget():
    with pytest.raises(SystemExit):main(['run','--allow-network'])

def test_schema_cli_only_finish(capsys):
    assert main(['schema','--final'])==0
    assert len(loads(capsys.readouterr().out))==1
