import json
from pathlib import Path
import pytest
import trace_hard_cohort_a3 as cohort
import trace_question_a3 as previous
from test_trace_question_a3 import ledger


def plan(tmp_path, count=12, cap=1000, used=62):
    budget = tmp_path / 'synthetic.sqlite'; ledger(budget, cap, used)
    entries = []
    for i in range(count):
        q = tmp_path / f'q{i}.json'; cohort.trace.save(q, {'qid': str(i), 'question': 'Synthetic only'})
        p = dict(qid=str(i), question_path=str(q), question_sha256=cohort.trace.sha(q),
                 output=str(tmp_path / f'episode{i}'), config=cohort.trace.config().to_dict(),
                 source_hashes=cohort.trace.source_hashes(), collector_sha256=cohort.trace.sha(cohort.trace.__file__),
                 budget_path=str(budget))
        pp = tmp_path / f'p{i}.json'; cohort.trace.save(pp, p)
        entries.append({'path': str(pp), 'sha256': cohort.trace.sha(pp)})
    cp = tmp_path / 'cohort.json'
    cohort.trace.save(cp, {'plans': entries, 'qids': [str(i) for i in range(count)], 'judge_reserve': count,
                          'runner_sha256': cohort.trace.sha(cohort.__file__), 'status_dir': str(tmp_path / 'status')})
    return cp, budget


def test_only_budget_fields_change():
    before = previous.config().to_dict(); after = cohort.trace.config().to_dict()
    expected = {'max_model_calls': 64, 'max_actions': 200, 'max_backend_calls': 120,
                'max_total_output_tokens': 48000, 'max_seconds': 1800}
    assert {k: v for k, v in after.items() if v != before[k]} == expected


@pytest.mark.parametrize('used,passes', [(62, True), (221, False)])
def test_full_780_request_coverage(tmp_path, used, passes):
    cp, budget = plan(tmp_path, used=used)
    before = budget.read_bytes()
    if passes:
        assert len(cohort.preflight(cp)[1]) == 12
    else:
        with pytest.raises(ValueError, match='BLOCKED_BUDGET'): cohort.preflight(cp)
    assert budget.read_bytes() == before


@pytest.mark.parametrize('terminal,continued', [('abstained', True), ('context_capacity', True), ('http_error', False)])
def test_no_retry_and_only_infrastructure_stops_queue(tmp_path, monkeypatch, terminal, continued):
    cp, budget = plan(tmp_path, count=2); calls = []
    def fake_run(path):
        p = json.loads(Path(path).read_text()); calls.append(p['qid'])
        root = Path(p['output']); root.mkdir()
        cohort.trace.save(root / 'result.json', {'terminal': {'outcome': terminal}, 'http_attempts': 0})
    monkeypatch.setattr(cohort.trace, 'run', fake_run)
    if continued: cohort.run(cp)
    else:
        with pytest.raises(RuntimeError): cohort.run(cp)
    assert calls == (['0', '1'] if continued else ['0'])
