"""Compound search preserves evidence delivery, resource and failure boundaries."""
from copy import deepcopy
import pytest

from stride_search import Config, Harness
from stride_search.contract import ContractError, loads, text_hash
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import AnthropicModel, HTTP
from stride_search.workflow_contract import WorkflowConfig
from test_middle_history import preview, step


PROTOCOL = 'search-raw-window-v1'
SEARCH = ('search', {'queries': ['Lumen']})


class Pages:
    identity = {'kind': 'synthetic-fixed-search', 'index_id': 'raw-window-boundaries-1'}

    def __init__(self, pages, routes):
        self.pages, self.routes = pages, routes
        self.gets = []

    def search(self, query, top_k):
        return [{'docid': d, 'title': d, 'snippet': 'Navigation only: invented snippet value 999.'}
                for d in self.routes.get(query, [])[:top_k]]

    def get_document(self, docid):
        self.gets.append(docid)
        value = self.pages[docid]
        if isinstance(value, Exception):
            raise value
        return {'docid': docid, 'content': value}


def make(retriever=None, *, protocol=PROTOCOL, workflow=None, **config):
    return Harness('Who directed Lumen?', retriever or smoke_corpus(),
        decision_protocol=protocol, workflow=workflow,
        config=Config(**{'max_model_calls': 20, **config}))


def results(h):
    return [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result']


def events(h, kind):
    return [e['payload'] for e in h.archive.events() if e['kind'] == kind]


@pytest.mark.parametrize('profile', ['legacy', 'full'])
@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_schema_and_nonsearch_descriptions_unchanged_actual_wire(profile, provider):
    a = make(protocol='baseline', workflow=WorkflowConfig.profile(profile))
    b = make(workflow=WorkflowConfig.profile(profile))
    model = None if provider == 'openai' else AnthropicModel(
        'http://fixture.invalid', 'fixture', revision='fixture', http=HTTP())
    try:
        old, new = preview(a, model=model), preview(b, model=model)
        def functions(wire):
            return {t.get('function', t)['name']: t.get('function', t) for t in wire['tools']}
        old_tools, new_tools = functions(old['wire']), functions(new['wire'])
        assert old_tools.keys() == new_tools.keys()
        for name in old_tools:
            x, y = deepcopy(old_tools[name]), deepcopy(new_tools[name])
            if name == 'search':
                assert x.pop('description') != y.pop('description')
                assert 'does NOT open' not in new_tools[name]['description']
            assert x == y
        assert old['wire'].get('tool_choice') == new['wire'].get('tool_choice')
        assert new['capacity'] == b.counter(new['wire'])
        before, seq = deepcopy(b.search_raw.__dict__), b.archive.seq
        assert preview(b, model=model) == new
        assert b.archive.seq == seq and b.search_raw.__dict__ == before
    finally:
        a.close(); b.close()


def test_first_query_first_document_only_and_no_sibling_fallback():
    backend = Pages({'a': 'alpha raw', 'b': 'beta raw'},
                    {'alpha': ['a', 'b'], 'beta': ['b'], 'empty': []})
    h = make(backend)
    try:
        step(h, ('search', {'queries': ['empty', 'beta']}))
        assert not backend.gets and not h.groups[-1]['evidence']
        step(h, ('search', {'queries': ['alpha', 'beta']}))
        assert backend.gets == ['a'] and h.groups[-1]['evidence'] == ['e1']
        assert len(results(h)[-1]['result']['results']) == 2
        step(h, ('search', {'queries': ['alpha', 'beta']}))
        assert backend.gets == ['a'] and not h.groups[-1]['evidence']
        assert len(events(h, 'query_execution')) == 6
        assert h.action_slots == 3 and h.backend_calls == 4
    finally:
        h.close()


def test_no_match_consumes_attempt_without_promoting_snippet_or_retry():
    backend = Pages({'a': 'Actual unconnected prose.'}, {'phantom': ['a'], 'Actual': ['a']})
    h = make(backend)
    try:
        step(h, ('search', {'queries': ['phantom']}))
        assert results(h)[0]['result']['ok'] and not h.groups[-1]['evidence']
        assert not h.exposed
        step(h, ('search', {'queries': ['Actual']}))
        assert backend.gets == ['a'] and not h.groups[-1]['evidence']
        assert len(events(h, 'search_raw_attempt')) == 1
        with pytest.raises(ContractError):
            h.archive.evidence('e1')
    finally:
        h.close()


def test_six_attempt_cap_does_not_stop_native_search_or_later_read():
    pages = {f'doc{i}': f'phrase{i} raw record' for i in range(7)}
    backend = Pages(pages, {f'phrase{i}': [f'doc{i}'] for i in range(7)})
    h = make(backend)
    try:
        for i in range(7):
            step(h, ('search', {'queries': [f'phrase{i}']}))
        assert len(backend.gets) == 6 and len(events(h, 'search_raw_attempt')) == 6
        assert not h.groups[-1]['evidence'] and h.terminal is None
        step(h, ('read', {'ref': 'd7'}))
        assert h.groups[-1]['evidence'] == ['e7'] and len(backend.gets) == 7
        assert h.action_slots == 8 and h.backend_calls == 14
    finally:
        h.close()


@pytest.mark.parametrize('cached', [False, True])
def test_exhausted_backend_skips_only_uncached_snapshot(cached):
    h = make(max_backend_calls=1)
    try:
        if cached:
            d = h.archive.register_doc('archive-entry', 'Lumen Observatory record')
            h.archive.snapshot(d, 'Lumen original cached source.')
        step(h)
        assert h.backend_calls == 1 and h.terminal is None
        assert bool(h.groups[-1]['evidence']) == cached
        assert len(events(h, 'search_raw_attempt')) == int(cached)
    finally:
        h.close()


@pytest.mark.parametrize('length', [80, 3000, 6000])
def test_unicode_contiguous_original_window_and_configured_length(length):
    raw = '无关段落🙂 ' * 600 + '\n\nİstanbul Lumen 数据原文🙂 ' * 200
    h = make(Pages({'a': raw}, {'İstanbul Lumen': ['a']}), read_chars=length)
    try:
        step(h, ('search', {'queries': ['İstanbul Lumen']}))
        view = h.archive.evidence('e1')
        assert view['text'] == raw[view['start']:view['end']]
        assert len(view['text']) <= min(length, 3000)
        assert h.archive.get(view['snapshot']) == raw
        assert text_hash(view['text']) == view['sha256']
        assert 'invented snippet value' not in view['text']
    finally:
        h.close()


def test_whole_result_withholding_retains_execution_not_authority():
    h = make()
    try:
        def counter(wire):
            has_raw = any(m.get('role') == 'tool' and loads(m['content']).get('raw_windows')
                          for m in wire.get('messages', []))
            return h.config.context_limit if has_raw else 1
        counter.identity = {'kind': 'synthetic-capacity-boundary'}
        h.counter = counter
        step(h)
        assert results(h)[-1]['result']['code'] == 'result_capacity'
        assert h.groups[-1]['evidence'] == [] and h.groups[-1]['documents'] == []
        assert not h.exposed and not h.published_docs
        assert h.archive.evidence('e1')['text']
        assert h.backend_calls == 2 and len(events(h, 'search_raw_attempt')) == 1
        step(h, ('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}))
        assert h.terminal is None and results(h)[-1]['result']['code'] == 'unreceived_reference'
        assert not h.exposed
    finally:
        h.close()


def test_get_failure_seals_partial_search_and_unexecuted_suffix():
    h = make(Pages({'a': TimeoutError('local fixture')}, {'alpha': ['a']}))
    try:
        model = ScriptedModel([native(('search', {'queries': ['alpha']}),
                                      ('finish', {'abstain': True, 'reason': 'fixture'}))])
        h._step(model)
        assert h.terminal['outcome'] == 'backend_failure'
        assert h.backend_calls == 2 and h.action_slots == 1
        assert results(h)[1]['result']['code'] == 'not_executed'
        assert not h.groups[-1]['documents'] and not h.groups[-1]['evidence']
        assert not h.exposed and len(events(h, 'search_raw_attempt')) == 1
        saved = events(h, 'search_raw_navigation')[0]
        assert loads(h.archive.get(saved['navigation_object']))['results'][0]['hits'][0]['ref'] == 'd1'
        assert h.archive.verify()
    finally:
        h.close()


def test_final_prevents_compound_search_and_new_raw_progress_needs_ack():
    h = make(workflow=WorkflowConfig.profile('full'), max_model_calls=3)
    try:
        step(h)
        assert h.workflow.raw_seen == set() and not h.exposed
        step(h, ('read', {'ref': 'e1'}))
        assert h.workflow.raw_seen == {'e1'} and h.workflow.last_new_raw == 1
        assert h.backend_calls == 2
        step(h, SEARCH)
        assert results(h)[-1]['result']['code'] == 'final_only'
        assert h.workflow.raw_seen == {'e1'} and h.workflow.last_new_raw == 1
        assert len(events(h, 'search_raw_attempt')) == 1 and h.backend_calls == 2
    finally:
        h.close()


@pytest.mark.parametrize('expire_at', ['search', 'get'])
def test_local_time_boundary_before_and_after_automatic_attempt(expire_at):
    clock = [0.0]

    class TimedPages(Pages):
        def search(self, query, top_k):
            value = super().search(query, top_k)
            if expire_at == 'search':
                clock[0] = 601.0
            return value

        def get_document(self, docid):
            value = super().get_document(docid)
            if expire_at == 'get':
                clock[0] = 601.0
            return value

    h = make(TimedPages({'a': 'alpha original record'}, {'alpha': ['a']}), max_seconds=600)
    h.clock, h.started = lambda: clock[0], 0.0
    try:
        h._step(ScriptedModel([native(('search', {'queries': ['alpha']}),
            ('finish', {'abstain': True, 'reason': 'fixture'}))]))
        assert h.terminal['outcome'] == 'time_budget'
        assert len(events(h, 'search_raw_attempt')) == int(expire_at == 'get')
        assert h.backend_calls == (2 if expire_at == 'get' else 1)
        assert bool(h.archive.doc('d1')['snapshot']) == (expire_at == 'get')
        assert len(events(h, 'search_raw_navigation')) == 1
        assert results(h)[1]['result']['code'] == 'not_executed'
        assert not h.exposed and not h.groups[-1]['evidence'] and h.archive.verify()
    finally:
        h.close()


def test_withheld_window_needs_later_native_read_and_is_not_auto_retried():
    h = make()
    try:
        def counter(wire):
            return h.config.context_limit if any(m.get('role') == 'tool'
                and loads(m['content']).get('raw_windows') for m in wire['messages']) else 1
        counter.identity = {'kind': 'synthetic-capacity-boundary'}
        h.counter = counter
        step(h)
        assert results(h)[-1]['result']['code'] == 'result_capacity'
        step(h)
        assert results(h)[-1]['result']['ok'] and not h.groups[-1]['evidence']
        assert len(events(h, 'search_raw_attempt')) == 1 and not h.exposed
        step(h, ('read', {'ref': 'd1'}))
        assert h.groups[-1]['evidence'] == ['e1'] and not h.exposed
        step(h, ('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}))
        assert h.terminal['outcome'] == 'submitted' and h.exposed == {'e1'}
        assert h.backend_calls == 2 and len(events(h, 'search_raw_attempt')) == 1
    finally:
        h.close()
