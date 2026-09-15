"""Synthetic coverage-rank checks; no live model or research-question requests."""
from copy import deepcopy
import json

import pytest

from stride_search import Config, Harness, cli
from stride_search import coverage_rank, search_support
from stride_search.archive import Archive
from stride_search.contract import ContractError, digest, canonical
from stride_search.cpu_index import SQLiteFTS5
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from test_cpu_index import make_index


def row(docid, title='', snippet='', score=1.0):
    return dict(docid=docid, title=title, snippet=snippet, score=score)


def compiled(*terms):
    return dict(compiler='cpu-or-1', terms=list(terms), expression=' OR '.join(terms))


def test_exact_unicode_terms_full_fields_stable_ties_and_original_scores():
    rows = [row('substring', snippet='Lumenology directors'),
            row('one', snippet='LUMEN Lumen lumen'),
            row('two', title='Straße', snippet='x ' * 300 + ' Lumen'),
            row('tie', title='STRASSE Lumen', score=-9.0)]
    before = deepcopy(rows)
    selected, audit = coverage_rank.rank(rows, compiled('lumen', 'LUMEN', 'strasse'), 4)
    assert [r['docid'] for r in selected] == ['two', 'tie', 'one', 'substring']
    assert rows == before and selected[1]['score'] == -9.0
    assert audit['query_terms'] == ['lumen', 'strasse']
    assert [a['coverage'] for a in audit['candidates']] == [0, 1, 2, 2]
    assert [a['reranked_rank'] for a in audit['candidates']] == [4, 3, 1, 2]
    assert audit['candidate_pool_sha256'] == digest(rows)
    assert audit['selected_rows_sha256'] == digest(selected)
    assert coverage_rank.rank([row('stop', snippet='the')], compiled('the'), 1)[1]['candidates'][0]['coverage'] == 1


@pytest.mark.parametrize('top_k', range(1, 21))
def test_all_legal_return_counts(top_k):
    pool = [row(str(i), snippet='Lumen') for i in range(20)]
    selected, audit = coverage_rank.rank(pool, compiled('lumen'), top_k)
    assert selected == pool[:top_k]
    assert sum(c['selected'] for c in audit['candidates']) == top_k


@pytest.mark.parametrize('top_k', [0, 21, True, 1.5, '2'])
def test_invalid_top_k_rejected(top_k):
    with pytest.raises(ContractError):
        coverage_rank.rank([], compiled('lumen'), top_k)


@pytest.mark.parametrize('pool', [None, {}, [row('x')] * 21,
    [row('x'), row('x')], [row('good'), {'docid': 'bad', 'title': 'bad'}],
    [row('x', score=float('nan'))], [row('x', score=True)], [row('', snippet='bad')]])
def test_entire_pool_validated_before_selection(pool):
    with pytest.raises(ContractError) as error:
        coverage_rank.rank(pool, compiled('lumen'), 1)
    assert error.value.fatal


@pytest.mark.parametrize('value', [None, {}, compiled(''),
    dict(compiler='unknown', terms=['lumen'], expression='lumen'),
    dict(compiler='cpu-or-1', terms='lumen', expression='lumen')])
def test_unknown_or_invalid_compiler_rejected(value):
    with pytest.raises(ContractError):
        coverage_rank.rank([], value, 1)


def test_unknown_retriever_rejected_before_creating_archive(tmp_path):
    db = tmp_path / 'must-not-exist.sqlite'
    with pytest.raises(ValueError, match='stride-cpu-or-1'):
        Harness('Synthetic?', smoke_corpus(), path=db, decision_protocol='search-coverage-rank-v1')
    assert not db.exists()


def test_empty_pool_and_zero_overlap_preserve_upstream_order():
    assert coverage_rank.rank([], compiled(), 20)[0] == []
    pool = [row('b', snippet='other'), row('a', snippet='unrelated')]
    assert coverage_rank.rank(pool, compiled('lumen'), 20)[0] == pool


@pytest.fixture
def cpu(tmp_path):
    index = SQLiteFTS5(make_index(tmp_path / 'index.sqlite', docs=[
        ('a', 'Lumen ' * 20, 'https://fixture.example/a'),
        ('b', 'Lumen director Ada Rowan.', 'https://fixture.example/b'),
        ('c', 'director ' * 20, 'https://fixture.example/c'),
    ]), index_id='synthetic-coverage')
    yield index
    index.close()


def test_real_backend_pool_cache_key_scope_and_capabilities(cpu, monkeypatch):
    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1')
    try:
        args = {'queries': ['Lumen director'], 'top_k': 1}
        baseline_key = search_support.query_spec(h, args['queries'][0], 1)[0]
        result, docs, evidence = h._dispatch('search', args, {'documents': [], 'evidence': []})
        assert docs == ['d1'] and evidence == [] and not h.exposed and not h.published_docs
        assert h.archive.doc('d1')['backend'] == 'b'
        assert h.archive.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 1
        assert cpu.last_wire_request['top_k'] == 20
        assert h.backend_calls == 1 and baseline_key not in h.search_cache
        assert len(next(iter(h.search_cache.values()))) == 1
        events = list(h.archive.events())
        audit = next(e['payload'] for e in events if e['kind'] == 'search_coverage_rank')
        backend = next(e['payload'] for e in events if e['kind'] == 'backend_response')
        pool = h.archive.json(audit['candidate_pool_object'])
        assert pool == h.archive.json(backend['object']) == h.archive.json(backend['raw_wire'])
        assert len(pool) == 3 and audit['selected_docids'] == ['b']
        assert h.search_capabilities['upstream_ranking'] == cpu.capabilities['ranking']
        assert 'coverage' in h.search_capabilities['ranking']
        assert cpu.capabilities['ranking'] == h.search_capabilities['upstream_ranking']
        monkeypatch.setattr(cpu, 'search', lambda *args: pytest.fail('cache hit called backend'))
        monkeypatch.setattr(coverage_rank, 'rank', lambda *args: pytest.fail('cache hit reranked'))
        cached, _, _ = h._dispatch('search', args, {'documents': [], 'evidence': []})
        assert cached['results'][0]['cached'] is True
        assert result['results'][0]['hits'] == cached['results'][0]['hits']
        assert h.backend_calls == 1
        assert len([e for e in h.archive.events() if e['kind'] == 'search_coverage_rank']) == 1
        key = coverage_rank.query_spec(search_support.query_spec(h, 'Lumen director', 1))[0]
        other_top_k = coverage_rank.query_spec(search_support.query_spec(h, 'Lumen director', 2))[0]
        assert key != other_top_k
        monkeypatch.setitem(coverage_rank.RULE, 'ranking', 'test-version-change')
        assert coverage_rank.query_spec(search_support.query_spec(h, 'Lumen director', 1))[0] != key
    finally:
        h.close()


def test_malformed_unselected_hit_fails_without_registering_docs(cpu, monkeypatch):
    monkeypatch.setattr(cpu, 'search', lambda *args: [row('valid', snippet='Lumen'), {'docid': 'bad'}])
    h = Harness('Synthetic?', cpu, decision_protocol='search-coverage-rank-v1')
    try:
        with pytest.raises(ContractError):
            h._dispatch('search', {'queries': ['Lumen'], 'top_k': 1}, {'documents': [], 'evidence': []})
        assert h.archive.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 0
        assert not h.search_cache
        assert any(e['kind'] == 'backend_response' for e in h.archive.events())
    finally:
        h.close()


def test_compiled_equivalent_cache_reuses_final_selection(cpu, monkeypatch):
    h = Harness('Synthetic?', cpu, config=Config(compiled_query_cache=True),
                decision_protocol='search-coverage-rank-v1')
    try:
        binding = {'documents': [], 'evidence': []}
        first, _, _ = h._dispatch('search', {'queries': ['Lumen director'], 'top_k': 1}, binding)
        monkeypatch.setattr(cpu, 'search', lambda *args: pytest.fail('equivalent cache called CPU'))
        second, _, _ = h._dispatch('search', {'queries': ['LUMEN director Lumen'], 'top_k': 1}, binding)
        assert second['results'][0]['cached'] is True
        assert second['results'][0]['hits'] == first['results'][0]['hits']
        assert h.backend_calls == 1
    finally:
        h.close()


def test_default_baseline_wire_and_results_unchanged_and_candidate_tools_unchanged(cpu):
    replies = [native(('search', {'queries': ['Lumen director'], 'top_k': 1})),
               native(('finish', {'abstain': True, 'reason': 'Synthetic control'}))]
    histories = []
    for options in [{}, {'decision_protocol': 'baseline'}, {'decision_protocol': 'search-coverage-rank-v1'}]:
        h = Harness('Synthetic?', cpu, config=Config(max_model_calls=3), **options)
        model = ScriptedModel(replies)
        try:
            h.run(model)
            result = next(e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result')
            histories.append((model.requests, result))
            assert h.search_raw is None and h.once_prose is None
        finally:
            h.close()
    assert histories[0] == histories[1]
    assert histories[0][0][0]['tools'] == histories[2][0][0]['tools']
    assert histories[0][0][0]['messages'][0] == histories[2][0][0]['messages'][0]
    assert 'coverage_reranking' in json.dumps(histories[2][0][0])
    base_wire = histories[0][0][0]
    candidate_wire = deepcopy(histories[2][0][0])
    prefix, candidate_control = candidate_wire['messages'][-1]['content'].split('\n', 1)
    base_control = json.loads(base_wire['messages'][-1]['content'].split('\n', 1)[1])
    control = json.loads(candidate_control)
    control['retriever_capabilities'] = base_control['retriever_capabilities']
    candidate_wire['messages'][-1]['content'] = prefix + '\n' + canonical(control)
    assert candidate_wire == base_wire


def test_cli_sqlite_source_authorization_archive_and_replay(cpu, tmp_path, monkeypatch, capsys):
    model = ScriptedModel([
        native(('search', {'queries': ['Lumen director'], 'top_k': 1}), ('read', {'ref': 'd1'})),
        native(('finish', {'answer': 'Ada Rowan', 'refs': ['e1']})),
        native(('read', {'ref': 'd2'}), ('read', {'ref': 'd1'})),
        native(('finish', {'answer': 'Ada Rowan', 'refs': ['e1']})),
    ])
    monkeypatch.setattr(cli, '_model', lambda *args: model)
    path = tmp_path / 'index.sqlite'
    before = path.read_bytes()
    question = tmp_path / 'question.txt'; question.write_text('Who directed Lumen?', encoding='utf-8')
    db = tmp_path / 'episode.sqlite'
    assert cli.main(['run', '--allow-network', '--accept-counter-estimate',
        '--base-url', 'http://fixture.invalid', '--model', 'fixture', '--model-revision', 'synthetic',
        '--sqlite-index', str(path), '--index-id', 'synthetic-coverage', '--counter', 'utf8_bytes',
        '--question-file', str(question), '--db', str(db), '--max-model-calls', '5',
        '--context-limit', '100000', '--response-reserve', '8192',
        '--decision-protocol', 'search-coverage-rank-v1']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['terminal']['answer'] == 'Ada Rowan' and report['terminal']['refs'] == ['e1']
    assert report['backend_attempts'] == 2
    assert report['action_error_counts']['unreceived_reference'] == 3
    assert path.read_bytes() == before
    a = Archive(db, readonly=True)
    try:
        assert a.verify()['head'] == report['head']
        assert [a.load_request(e['payload']['request']) for e in a.events() if e['kind'] == 'model_request'] == model.requests
        assert a.db.execute('SELECT count(*) FROM docs').fetchone()[0] == 1
        assert a.doc('d1')['backend'] == 'b'
        assert a.evidence('e1')['text'] == 'Lumen director Ada Rowan.'
    finally:
        a.close()
    assert cli.main(['replay', '--db', str(db)]) == 0
    assert json.loads(capsys.readouterr().out) == report
