"""Selection leakage boundaries and question-cluster uncertainty on synthetic outcomes."""
import importlib.util
from pathlib import Path
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from freeze_development import classify
from compare_strong_api import effect, clustered
from strong_api_freeze_guard import check_episode_input,check_final_freeze,PROCEDURE_SOURCES
import json


def row(correct=True, **changes):
    return {'correct':correct,'outcome':'submitted','backend_requests':3,'online_model_requests':7,
            'elapsed_seconds':10,'input_tokens_measured':100,'output_tokens_measured':20,**changes}


def test_difficulty_does_not_turn_infrastructure_failure_into_hard_question():
    assert classify([row(False,outcome='context_overflow')]*2)[0]=='diagnostic'
    assert classify([row(False,calibration_excluded=True)]*2)[0]=='diagnostic'
    assert classify([row(False,evaluation_disputed=True)]*2)[0]=='diagnostic'
    assert classify([row(False)]*2)[0]=='hard'
    assert classify([row(True)])[0]=='medium'
    assert classify([row(True)]*2)[0]=='easy'
    with pytest.raises(ValueError,match='judged'):classify([row(None)])


def test_failed_fast_episode_never_counts_as_faster_correct_completion():
    result=effect([(row(),row(False,elapsed_seconds=1))])
    assert result['accuracy_difference_pp']==-100
    assert result['correct_completion_time_change'] is None
    assert result['both_correct_pairs']==0


def test_bootstrap_preserves_all_replicates_of_same_question():
    # One stratum with one question has fixed within-question accuracy difference,
    # although its two replicate effects are opposite. Resampling episodes would vary.
    pairs={'q':[(row(True),row(False)),(row(False),row(True))]}
    result=clustered(pairs,{'q':'medium'},draws=100)
    assert result['accuracy_difference_pp']['percentile_95']==[0,0]
    assert 'correct_completion_time_change' not in result


def test_direct_episode_entry_cannot_bypass_sealed_confirmation_or_pilot_allowance(tmp_path):
    with pytest.raises(ValueError,match='sealed'):check_episode_input(tmp_path,'confirmation','q','fixture','B')
    splits=tmp_path/'dataset_splits';splits.mkdir()
    (splits/'pilot.questions.jsonl').write_text(json.dumps({'qid':'q','question':'fixture'})+'\n')
    with pytest.raises(ValueError,match='frozen'):check_episode_input(tmp_path,'pilot','q','changed','B')
    for n in range(2):
        p=tmp_path/f'{n}_pilot_B_q_{n}';p.mkdir();(p/'manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='exhausted'):check_episode_input(tmp_path,'pilot','q','fixture','B')


def test_confirmation_guard_rejects_post_freeze_code_change(tmp_path):
    snap={'source_hashes':{k:'original' for k in PROCEDURE_SOURCES}}
    record={'online_sources':{},'settings':{},'source_snapshot':snap,'sealed_files':{},'confirmation_plan':{'arms':['B','E-off']}}
    (tmp_path/'FINAL_FREEZE.json').write_text(json.dumps(record))
    assert check_final_freeze(tmp_path,snap,{})==record
    snap['source_hashes'][PROCEDURE_SOURCES[0]]='changed'
    with pytest.raises(ValueError,match='procedure changed'):check_final_freeze(tmp_path,snap,{})
