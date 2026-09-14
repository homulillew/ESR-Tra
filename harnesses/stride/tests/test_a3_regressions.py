"""Desired a3 behavior; synthetic contracts, not scored q26 replays."""
from stride_search import Config, Harness
from stride_search.context import build
from stride_search.contract import canonical
from stride_search.fixtures import ScriptedModel, native
from stride_search.providers import ByteCounter, LocalCorpus


def corpus():
    return LocalCorpus([
        {'docid': 'a', 'title': 'Alpha journal', 'content': 'Alpha candidate-marker owns the venue.'},
        {'docid': 'b', 'title': 'Beta unrelated person', 'content': 'Beta is a different person.'},
    ])


def test_acknowledged_key_window_survives_unrelated_read_and_compaction():
    class GroupCounter(ByteCounter):
        def __call__(self, wire):
            return 50000 * sum(m['role'] == 'assistant' for m in wire['messages']) + 100
    h = Harness('Identify the venue', corpus(), config=Config(max_model_calls=12, recent_groups=1), counter=GroupCounter())
    m = ScriptedModel([
        native(('search', {'queries': ['Alpha']})),
        native(('read', {'ref': 'd1'})),
        native(('search', {'queries': ['Beta']})),
        native(('read', {'ref': 'd2'})),
        native(('search', {'queries': ['Beta again']})),
    ])
    try:
        for _ in range(5): h._step(m)
        plan = build(h, m, h.counter, final=False, output_limit=2048)
        assert 'e1' in h.exposed
        assert 'candidate-marker' in canonical(plan['wire'])
        assert 'e1' in plan['visible']
    finally: h.close()


def test_recall_of_delivered_but_unopened_search_hit():
    h = Harness('Q', corpus(), config=Config(max_model_calls=5))
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('recall', {'query': 'Alpha'}))])
    try:
        for _ in range(2): h._step(m)
        rows = [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result']
        assert any(r.get('ref') == 'd1' and r['kind'] == 'search_hit_navigation' for r in rows[-1]['result']['matches'])
        assert not h.exposed
    finally: h.close()


def test_recall_excerpt_includes_match_near_end():
    c = LocalCorpus([{'docid': 'a', 'title': 'Alpha', 'content': 'x' * 900 + ' NEEDLE-MARKER owns the venue.'}])
    h = Harness('Q', c, config=Config(max_model_calls=5))
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('read', {'ref': 'd1'})),
                       native(('recall', {'query': 'NEEDLE-MARKER'}))])
    try:
        for _ in range(3): h._step(m)
        rows = [e['payload'] for e in h.archive.events() if e['kind'] == 'action_result']
        assert 'NEEDLE-MARKER' in rows[-1]['result']['matches'][0]['excerpt']
    finally: h.close()
