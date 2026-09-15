"""Independent batch, partial-failure and withholding checks; no network calls."""
from copy import deepcopy
import json

import pytest

from stride_search import Config, Harness
from stride_search.contract import canonical
from stride_search.fixtures import ScriptedModel, native
from stride_search.providers import ByteCounter
from test_coverage_rank import cpu


ABSTAIN = native(('finish', {'abstain': True, 'reason': 'Synthetic boundary fixture'}))


def actions(h):
    return [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result']


@pytest.mark.parametrize('queries,compiled_cache', [
    (['Lumen director', 'Lumen director'], False),
    (['Lumen director', 'LUMEN director Lumen'], True),
])
def test_batch_duplicate_or_compiled_equivalent_fetches_once_with_one_budget(cpu, queries, compiled_cache):
    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1',
                config=Config(max_model_calls=3, max_backend_calls=1, compiled_query_cache=compiled_cache))
    calls = ([('search', {'queries': queries, 'top_k': 1})] if compiled_cache else
             [('search', {'queries': [query], 'top_k': 1}) for query in queries])
    model = ScriptedModel([native(*calls), ABSTAIN])
    try:
        assert h.run(model)['outcome'] == 'abstained'
        batches = [batch for action in actions(h) if action['tool'] == 'search'
                   for batch in action['result']['results']]
        assert [batch['cached'] for batch in batches] == [False, True]
        assert batches[0]['hits'] == batches[1]['hits']
        assert h.backend_calls == 1
        events = list(h.archive.events())
        assert len([e for e in events if e['kind'] == 'search_coverage_rank']) == 1
        backend = next(e['payload'] for e in events if e['kind'] == 'backend_request')
        assert backend['arguments']['top_k'] == 20
        assert h.archive.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 1
        h.archive.verify()
    finally:
        h.close()


def test_batch_insufficient_budget_executes_no_backend_or_partial_query(cpu):
    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1',
                config=Config(max_model_calls=3, max_backend_calls=1))
    model = ScriptedModel([native(('search', {'queries': ['Lumen', 'director'], 'top_k': 1})), ABSTAIN])
    try:
        h.run(model)
        assert actions(h)[0]['result']['code'] == 'backend_budget'
        assert h.backend_calls == 0 and not h.search_cache
        assert not any(e['kind'] in ('query_execution', 'backend_request', 'search_coverage_rank')
                       for e in h.archive.events())
        assert h.archive.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 0
        assert not h.published_docs and not h.exposed
    finally:
        h.close()


def test_run_second_query_malformed_retains_both_pools_without_delivering_partial_navigation(cpu, monkeypatch):
    original_search = cpu.search
    malformed = [{'docid': 'bad', 'title': 'Malformed fixture', 'snippet': 17, 'score': 1.0}]

    def search(query, top_k):
        if query == 'director':
            cpu.last_wire_request = {'kind': 'local_sql', 'query': query, 'top_k': top_k, **cpu.compile_query(query)}
            cpu.last_wire_response = deepcopy(malformed)
            return deepcopy(malformed)
        return original_search(query, top_k)

    monkeypatch.setattr(cpu, 'search', search)
    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1',
                config=Config(max_model_calls=3))
    response = native(('search', {'queries': ['Lumen', 'director'], 'top_k': 1}))
    model = ScriptedModel([response])
    try:
        assert h.run(model)['outcome'] == 'retrieval_protocol'
        assert h.model_calls == 1 and h.backend_calls == 2
        assert not h.published_docs and not h.exposed
        assert h.groups[0]['documents'] == [] and h.groups[0]['evidence'] == []
        events = list(h.archive.events())
        backend = [e['payload'] for e in events if e['kind'] == 'backend_response']
        assert len(backend) == 2
        assert h.archive.json(backend[1]['object']) == malformed
        assert h.archive.json(backend[1]['raw_wire']) == malformed
        ranking = [e['payload'] for e in events if e['kind'] == 'search_coverage_rank']
        assert len(ranking) == 1
        assert h.archive.json(ranking[0]['candidate_pool_object']) == h.archive.json(backend[0]['object'])
        assert len(h.search_cache) == 1
        assert h.archive.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 1
        assert actions(h)[0]['result']['code'] == 'retrieval_protocol'
        archived_response = next(e['payload']['raw'] for e in events if e['kind'] == 'model_response')
        assert h.archive.json(archived_response) == response
        h.archive.verify()
    finally:
        h.close()


def test_withheld_ranked_result_does_not_authorize_saved_document(cpu):
    class WithholdNavigation(ByteCounter):
        def __call__(self, wire):
            for message in wire.get('messages', []):
                content = message.get('content')
                if message.get('role') == 'tool' and isinstance(content, str):
                    result = json.loads(content)
                    if any(batch.get('hits') for batch in result.get('results', [])):
                        return 1000000
            return 1

    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1',
                config=Config(max_model_calls=4), counter=WithholdNavigation())
    model = ScriptedModel([
        native(('search', {'queries': ['Lumen director'], 'top_k': 1})),
        native(('read', {'ref': 'd1'})), ABSTAIN,
    ])
    try:
        assert h.run(model)['outcome'] == 'abstained'
        results = actions(h)
        assert results[0]['result']['code'] == 'result_capacity'
        assert results[1]['result']['code'] == 'unreceived_reference'
        assert h.backend_calls == 1 and not h.published_docs and not h.exposed
        assert h.archive.doc('d1')['backend'] == 'b'
        assert h.archive.doc('d1')['snapshot'] is None
        assert all(not g['documents'] and not g['evidence'] for g in h.groups)
        events = list(h.archive.events())
        assert any(e['kind'] == 'result_withheld' for e in events)
        rank = next(e['payload'] for e in events if e['kind'] == 'search_coverage_rank')
        assert len(h.archive.json(rank['candidate_pool_object'])) == 3
        assert rank['selected_docids'] == ['b']
        assert 'fixture.example/b' not in canonical(model.requests[1])
        assert all(not e['payload']['documents'] for e in events if e['kind'] == 'delivery_ack')
        h.archive.verify()
    finally:
        h.close()
