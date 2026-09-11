from copy import deepcopy
import json

import pytest

from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import MemoryRetriever
from esr_harness_v3.experiments import exact_prefix, freeze_this_plan, load_plan, run_fixture_cohort, summarize_cohort
from esr_harness_v3.protocol import digest
from esr_harness_v3.store import Ledger
from .conftest import DOCS


def test_frozen_fixture_queue_retains_failure_and_unexecuted_denominator(tmp_path):
    root = tmp_path / 'cohort'
    result = run_fixture_cohort(root)
    assert len(result['rows']) == 8
    assert [r['status'] for r in result['rows']] == ['submitted'] * 4 + ['service_error'] + ['NOT_RUN'] * 3
    assert sum(r.get('model_attempts', 0) for r in result['rows']) == 15
    assert sum(r.get('backend_calls', 0) for r in result['rows']) == 8
    assert sum(r.get('usage', {}).get('unknown_calls', 0) for r in result['rows']) == 15
    assert result['real_model_calls'] == 0 and result['formal_accuracy'] is None
    assert result['implementation_unchanged'] and result['stopped_because'] == 'service_error'
    plan = load_plan(root)
    a, b = deepcopy(plan['conditions']['this_on']), deepcopy(plan['conditions']['this_off'])
    assert a.pop('enable_this') is True and b.pop('enable_this') is False and a == b
    before = {p.name: p.read_bytes() for p in root.glob('*.json')}
    assert len(summarize_cohort(root)['rows']) == 8
    with pytest.raises(FileExistsError):
        run_fixture_cohort(root)
    assert before == {p.name: p.read_bytes() for p in root.glob('*.json')}
    ledger = Ledger(root/'0000.sqlite', readonly=True)
    try:
        events = ledger.verify()
        request = next(e['payload'] for e in reversed(events) if e['kind'] == 'policy_request')
        prefix = exact_prefix(ledger, request['decision'])
        assert prefix['request'] == request['request'] and prefix['binding']['this'] == 'o1'
        assert prefix['request_sha256'] == digest(request['request'])
        assert prefix['additional_labels_injected'] is False
    finally:
        ledger.close()


def test_unexecuted_plan_is_not_zero_accuracy_and_question_labels_are_rejected(tmp_path):
    root = tmp_path/'empty'
    freeze_this_plan(root, [{'id': 'q', 'question': 'Q'}], Config(), identity={'retriever': MemoryRetriever(DOCS).identity,
                                                                                 'usage_kind': 'not-run'})
    result = summarize_cohort(root)
    assert len(result['rows']) == 2 and result['formal_accuracy'] is None
    assert all(r['status'] == 'NOT_RUN' for r in result['rows'])
    with pytest.raises(ValueError, match='labels'):
        freeze_this_plan(tmp_path/'labelled', [{'id': 'q', 'question': 'Q', 'gold': 'A'}], Config(), identity={})


def test_changed_plan_and_wrong_episode_are_rejected(tmp_path):
    root = tmp_path/'mismatch'
    retriever = MemoryRetriever(DOCS)
    freeze_this_plan(root, [{'id': 'q', 'question': 'Q'}], Config(), identity={'retriever': retriever.identity, 'usage_kind': 'fixture'})
    h = Harness('Different Q', retriever, ledger=root/'0000.sqlite')
    h.close()
    with pytest.raises(ContractError, match='frozen'):
        summarize_cohort(root)
    path = root/'plan.json'
    wrapper = json.loads(path.read_text(encoding='utf-8'))
    wrapper['plan']['schedule'].pop()
    path.write_text(json.dumps(wrapper), encoding='utf-8')
    with pytest.raises(ContractError, match='changed'):
        load_plan(root)


def test_unsent_prefix_is_not_reconstructed():
    h = Harness('Q', MemoryRetriever(DOCS))
    try:
        d = h.begin()
        with pytest.raises(ContractError, match='recorded response'):
            exact_prefix(h.ledger, d.id)
    finally:
        h.close()
