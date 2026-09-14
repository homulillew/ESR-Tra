"""Synthetic SQLite tests; same SQL semantics as legacy LocalIndex, not BC+ scores."""
import json
import sqlite3
from pathlib import Path

import pytest

from stride_search import Config, Harness
from stride_search.cpu_index import SQLiteFTS5
from stride_search.contract import canonical, digest
from stride_search.diagnostics import diagnose
from stride_search.fixtures import ScriptedModel, native

DOCS = [
    ('a', 'Mira Stone directed Alpha. The second director was Ivo Lane.', 'https://other.example/a'),
    ('b', 'Mira is a common first name.', 'https://other.example/b'),
    ('c', 'Stone is a material.', 'https://other.example/c'),
    ('d', 'site target example site target example', 'https://other.example/d'),
]


def make_index(path, docs=DOCS, complete=True):
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE docs(docid TEXT,content TEXT,url TEXT); CREATE VIRTUAL TABLE search USING fts5(content,content='docs',content_rowid='rowid',tokenize='porter unicode61');")
    db.execute('INSERT INTO metadata VALUES (?,?)', ('identity', json.dumps({'complete': complete, 'documents': len(docs)})))
    db.executemany('INSERT INTO docs VALUES (?,?,?)', docs)
    db.execute("INSERT INTO search(search) VALUES ('rebuild')")
    db.commit(); db.close()
    return path


@pytest.fixture
def index(tmp_path):
    value = SQLiteFTS5(make_index(tmp_path / 'index.sqlite'), index_id='synthetic')
    yield value
    value.close()


@pytest.mark.parametrize('query', ['Mira Stone', '"Mira Stone"', '"Mira Stone" site:target.example',
                                  'Mira AND Stone', 'Mira OR "', '...', 'Mira Mira Stone', 'MIRA Stone'])
def test_same_raw_sql_ranking_and_snippet_as_legacy_localindex(index, query):
    import re
    terms = list(dict.fromkeys(re.findall(r'\w+', query.lower())))
    expression = ' OR '.join('"' + w.replace('"', '""') + '"' for w in terms)
    rows = [] if not expression else index.db.execute(
        "SELECT d.docid,d.url,snippet(search,0,'','',' ... ',48),bm25(search) "
        'FROM search JOIN docs d ON d.rowid=search.rowid WHERE search MATCH ? '
        'ORDER BY bm25(search),d.docid LIMIT ?', (expression, 10)).fetchall()
    expected = [{'docid': r[0], 'title': r[1], 'snippet': r[2], 'score': -r[3]} for r in rows]
    assert index.search(query, 10) == expected
    assert index.last_wire_request['expression'] == expression


def test_not_phrase_or_domain_filter(index):
    assert index.search('Mira Stone', 10) == index.search('"Mira Stone"', 10)
    ids = {r['docid'] for r in index.search('Mira Stone', 10)}
    assert {'a', 'b', 'c'} <= ids
    assert any('other.example' in r['title'] for r in index.search('Mira site:target.example', 10))
    assert index.capabilities['site_filter'] is False


def test_readonly_does_not_change_or_create_index(tmp_path):
    p = make_index(tmp_path / 'data.sqlite')
    before = p.read_bytes()
    with pytest.raises(sqlite3.OperationalError):
        SQLiteFTS5(tmp_path / 'missing.sqlite', index_id='x')
    assert not (tmp_path / 'missing.sqlite').exists()
    idx = SQLiteFTS5(p, index_id='x')
    with pytest.raises(sqlite3.OperationalError): idx.db.execute('DELETE FROM docs')
    idx.search('Mira', 3); idx.get_document('a'); idx.close()
    assert p.read_bytes() == before


@pytest.mark.parametrize('complete', [False, 1, None])
def test_incomplete_or_invalid_metadata_rejected(tmp_path, complete):
    p = make_index(tmp_path / 'index.sqlite', complete=complete)
    with pytest.raises(ValueError): SQLiteFTS5(p, index_id='x')


@pytest.mark.parametrize('k', [0, True, 1.0, 21])
def test_invalid_topk(index, k):
    with pytest.raises(ValueError): index.search('Mira', k)


@pytest.mark.parametrize('cache,expected', [(False, 2), (True, 1)])
def test_exact_compiler_cache_opt_in(index, tmp_path, cache, expected):
    h = Harness('Who directed Alpha?', index, path=tmp_path/'episode.sqlite',
                config=Config(max_model_calls=2, compiled_query_cache=cache, max_backend_calls=2))
    m = ScriptedModel([native(('search', {'queries': ['Mira Stone', '"Mira Stone"'], 'top_k': 3})),
                       native(('finish', {'abstain': True, 'reason': 'Only navigation, no raw reading'}))])
    try:
        h.run(m)
        assert h.backend_calls == expected
        assert not h.exposed
        q = [e['payload'] for e in h.archive.events() if e['kind'] == 'query_execution']
        assert q[0]['equivalence_key'] == q[1]['equivalence_key']
        assert q[1]['cached'] is cache
        results = [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result']
        assert results[0]['results'][0]['hits'][0]['ref'] == results[0]['results'][1]['hits'][0]['ref']
    finally: h.close()
    before = (tmp_path/'episode.sqlite').read_bytes()
    diagnostic = diagnose(tmp_path/'episode.sqlite')
    assert diagnostic['equivalent_query_repeats'] == 1
    assert not any('query' in q for q in diagnostic['queries'])
    assert (tmp_path/'episode.sqlite').read_bytes() == before
    assert diagnose(tmp_path/'episode.sqlite', include_text=True)['queries'][0]['compiled']['terms'] == ['mira', 'stone']


def test_compiled_batch_preflight_counts_unique_backend_work(index):
    h = Harness('Q', index, config=Config(max_model_calls=2, compiled_query_cache=True, max_backend_calls=1))
    try:
        h.run(ScriptedModel([native(('search', {'queries': ['Mira', '"Mira"']})),
                           native(('finish', {'abstain': True, 'reason': 'No raw evidence'}))]))
        assert h.backend_calls == 1
        assert h.terminal['outcome'] == 'abstained'
    finally: h.close()


def test_capabilities_are_backend_specific_and_can_be_hidden(index):
    from stride_search.context import build
    from stride_search.providers import ByteCounter, LocalCorpus
    for retriever, cpu in [(index, True), (LocalCorpus([{'docid':'x','title':'x','content':'x'}]), False)]:
        h = Harness('Q', retriever)
        try:
            wire = build(h, ScriptedModel([]), ByteCounter(), final=False, output_limit=100)['wire']
            text = canonical(wire)
            assert 'retriever_capabilities' in text
            assert ('first-occurrence deduplication' in text) is cpu
            assert '"max_calls_per_response":4' in wire['messages'][-1]['content']
        finally: h.close()
    h = Harness('Q', index, config=Config(disclose_retriever=False))
    try:
        assert 'retriever_capabilities' not in canonical(build(h, ScriptedModel([]), ByteCounter(), final=False, output_limit=100)['wire'])
    finally: h.close()


def test_topk_and_token_order_not_normalized_away(index):
    from stride_search.search_support import query_spec
    h = Harness('Q', index, config=Config(compiled_query_cache=True))
    try:
        a = query_spec(h, 'Mira Stone', 3)[0]
        assert a != query_spec(h, 'Stone Mira', 3)[0]
        assert a != query_spec(h, 'Mira Stone', 4)[0]
    finally: h.close()


def test_cpu_model_loop_no_gpu_imports(index):
    h = Harness('Who directed Alpha?', index, config=Config(max_model_calls=3))
    m = ScriptedModel([native(('search', {'queries': ['Alpha'], 'top_k': 1})),
                       native(('read', {'ref': 'd1'})), native(('finish', {'answer': 'Mira Stone', 'refs': ['e1']}))])
    try:
        h.run(m)
        assert h.terminal['outcome'] == 'submitted'
        assert h.backend_calls == 2
        assert h.terminal['semantic_status'] == 'not_automatically_verified'
        assert h.archive.report()['formal_correct'] is None
    finally: h.close()
