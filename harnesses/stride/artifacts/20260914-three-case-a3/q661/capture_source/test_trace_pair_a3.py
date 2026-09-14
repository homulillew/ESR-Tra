"""Offline budget coverage and isolation checks; never use a production ledger."""
import json
import pytest
import trace_pair_a3 as pair
from test_trace_question_a3 import ledger


def fixture_pair(tmp_path, cap=100, used=41, duplicate=False, extra_question_field=False):
    trace = pair.trace
    budget = tmp_path / 'synthetic-budget.sqlite'
    ledger(budget, cap, used)
    entries = []
    for i in range(2):
        qid = 'synthetic-0' if duplicate else f'synthetic-{i}'
        qpath = tmp_path / f'question-{i}.json'
        question = {'qid': qid, 'question': 'Synthetic question only'}
        if extra_question_field:
            question['answer'] = 'Synthetic forbidden extra field'
        trace.save(qpath, question)
        plan = dict(qid=qid, question_path=str(qpath), question_sha256=trace.sha(qpath),
                    output=str(tmp_path / f'output-{i}'), config=trace.config().to_dict(),
                    source_hashes=trace.source_hashes(), collector_sha256=trace.sha(trace.__file__),
                    budget_path=str(budget))
        plan_path = tmp_path / f'plan-{i}.json'
        trace.save(plan_path, plan)
        entries.append(dict(path=str(plan_path), sha256=trace.sha(plan_path)))
    path = tmp_path / 'pair.json'
    trace.save(path, {'plans': entries})
    return path, budget


@pytest.mark.parametrize('cap,valid', [(100, False), (105, True)])
def test_both_episodes_need_full_existing_budget(tmp_path, cap, valid):
    path, budget = fixture_pair(tmp_path, cap=cap)
    before = budget.read_bytes()
    if valid:
        assert len(pair.preflight(path)['plans']) == 2
    else:
        with pytest.raises(ValueError, match='remaining=59, required=64'):
            pair.preflight(path)
    assert budget.read_bytes() == before
    assert not list(tmp_path.glob('output-*'))


@pytest.mark.parametrize('option,match', [('duplicate', 'Duplicate episode'),
                                         ('extra_question_field', 'question-only')])
def test_isolation_before_network(tmp_path, option, match):
    path, budget = fixture_pair(tmp_path, cap=105, **{option: True})
    with pytest.raises(ValueError, match=match):
        pair.preflight(path)
    assert not list(tmp_path.glob('output-*'))
