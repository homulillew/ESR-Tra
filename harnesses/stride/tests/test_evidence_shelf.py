"""Raw retention and navigation are not semantic validation or extra observations."""
from dataclasses import replace
import json
import sqlite3

import pytest

from stride_search import Config, ContractError, Harness
from stride_search.archive import Archive
from stride_search.context import build
from stride_search.contract import canonical, validate
from stride_search.fixtures import ScriptedModel, native, smoke_corpus, smoke_model
from stride_search.providers import ByteCounter
from test_a3_regressions import corpus


def seeded(size=3):
    h = Harness('Q', corpus(), config=Config(evidence_shelf_size=size))
    for n in range(1, 5):
        d = h.archive.register_doc(f'doc{n}', f'Title {n}')
        h.archive.snapshot(d, f'Exact immutable source {n}.')
        e = h.archive.window(d, 0, 100)['ref']
        h.published_docs.add(d); h.doc_order.append(d)
        h.exposed.add(e); h.evidence_order.append(e)
    return h


def test_shelf_limit_first_delivery_order_and_zero_ablation():
    h = seeded(3)
    try:
        p = build(h, ScriptedModel([]), ByteCounter(), final=False, output_limit=100)
        assert p['shelf'] == ['e2', 'e3', 'e4']
        assert p['visible'] == ['e2', 'e3', 'e4']
        h.config = replace(h.config, evidence_shelf_size=0)
        p = build(h, ScriptedModel([]), ByteCounter(), final=False, output_limit=100)
        assert p['visible'] == []
    finally: h.close()


def test_shelf_exact_text_and_no_repeat_when_native_group_contains_source():
    h = Harness('Q', smoke_corpus(), config=Config(max_model_calls=5))
    m = smoke_model()
    try:
        for _ in range(2): h._step(m)
        p = build(h, m, h.counter, final=False, output_limit=100)
        assert p['shelf'] == []
        assert canonical(p['wire']).count('Its first director was Ada Rowan.') == 2
        h._step(m)
        h.groups = []
        p = build(h, m, h.counter, final=False, output_limit=100)
        raw_msg = next(x for x in p['wire']['messages'] if x['content'].startswith('Previously delivered raw'))
        restored = json.loads(raw_msg['content'].split('\n', 1)[1])
        assert restored[0]['text'] == h.archive.evidence('e1')['text']
        assert restored[0]['sha256'] == h.archive.evidence('e1')['sha256']
    finally: h.close()


def test_shelf_never_promotes_archive_only_window():
    h = seeded()
    try:
        h.exposed.remove('e4')
        p = build(h, ScriptedModel([]), ByteCounter(), final=False, output_limit=100)
        assert 'e4' not in p['visible']
        assert 'Exact immutable source 4.' not in canonical(p['wire'])
    finally: h.close()


def test_shelf_yields_to_capacity_and_emits_omission_not_hidden_exposure():
    h = seeded()
    class Counter(ByteCounter):
        def __call__(self, wire):
            return 1000000 if any(m['content'].startswith('Previously delivered raw') for m in wire['messages']) else 1
    try:
        p = build(h, ScriptedModel([]), Counter(), final=False, output_limit=100)
        assert p['shelf'] == [] and p['shelf_evicted'] == ['e2', 'e3', 'e4']
        assert p['visible'] == [] and len(h.exposed) == 4
    finally: h.close()


def test_navigation_is_ack_only_not_created_or_withheld():
    class Counter(ByteCounter):
        def __call__(self, wire):
            return 1000000 if any(m['role'] == 'tool' and '"hits"' in m['content'] for m in wire['messages']) else 1
    h = Harness('Q', corpus(), config=Config(max_model_calls=5), counter=Counter())
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('recall', {'query': 'Alpha'}))])
    try:
        h._step(m)
        assert h.archive.doc('d1') and not h.navigation_history
        h._step(m)
        assert not h.published_docs and not h.navigation_history
        result = [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]
        assert result['matches'] == []
    finally: h.close()


def test_navigation_ack_is_idempotent_and_source_not_citable():
    h = Harness('Q', corpus(), config=Config(max_model_calls=6))
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('recall', {'query': 'Alpha'})),
        native(('recall', {'query': 'Alpha'})), native(('finish', {'answer': 'Alpha', 'refs': ['d1']}))])
    try:
        for _ in range(4): h._step(m)
        assert len(h.navigation_history) == 1
        assert not h.exposed
        assert h.terminal is None
        assert h.archive.report()['action_error_counts']['arguments_invalid'] == 1
    finally: h.close()


def test_recall_navigation_off_and_center_off_reproduce_local_boundaries():
    h = Harness('Q', corpus(), config=Config(max_model_calls=5, recall_navigation=False))
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('recall', {'query': 'Alpha'}))])
    try:
        h._step(m); h._step(m)
        assert h.navigation_history
        assert [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]['matches'] == []
        from stride_search.search_support import excerpt
        assert excerpt('x'*500+' Marker', ['marker'], False)['excerpt'] == 'x'*400
        out = excerpt('α🙂'*500+' Marker', ['marker'], True)
        assert ('α🙂'*500+' Marker')[out['excerpt_start']:out['excerpt_end']] == out['excerpt']
        assert 'Marker' in out['excerpt']
    finally: h.close()


def test_deleted_navigation_object_is_detected(tmp_path):
    path = tmp_path/'episode.sqlite'
    h = Harness('Q', corpus(), path=path, config=Config(max_model_calls=2))
    h.run(ScriptedModel([native(('search', {'queries': ['Alpha']})), native(('finish', {'abstain': True, 'reason': 'No raw evidence'}))]))
    sha = next(e['payload']['object'] for e in h.archive.events() if e['kind'] == 'navigation_ack')
    h.close()
    db = sqlite3.connect(path); db.execute('DELETE FROM objects WHERE sha=?', (sha,)); db.commit(); db.close()
    with pytest.raises(ContractError): Archive(path, readonly=True)


@pytest.mark.parametrize('ignore_case, count', [(False, 0), (True, 1)])
def test_find_case_mode_exact_unicode_offsets(ignore_case, count):
    h = Harness('Q', corpus(), config=Config(max_model_calls=5))
    m = ScriptedModel([native(('search', {'queries': ['Alpha']})),
                       native(('find', {'ref': 'd1', 'text': 'ALPHA', 'ignore_case': ignore_case}))])
    try:
        h._step(m); h._step(m)
        row = [e['payload']['result'] for e in h.archive.events() if e['kind'] == 'action_result'][-1]
        assert len(row['matches']) == count and not h.exposed
        if count:
            full = h.archive.get(h.archive.doc('d1')['snapshot'])
            match = row['matches'][0]
            assert full[match['start']:match['end']] == 'Alpha'
    finally: h.close()


def test_wrong_answer_with_legal_ref_still_not_auto_verified():
    h = Harness('Who was first director?', smoke_corpus(), config=Config(max_model_calls=3))
    m = smoke_model(); m.responses[-1] = native(('finish', {'answer': 'Ivo Lane', 'refs': ['e1']}))
    try:
        h.run(m)
        assert h.terminal['outcome'] == 'submitted'
        assert h.terminal['semantic_status'] == 'not_automatically_verified'
        assert h.archive.report()['formal_correct'] is None
    finally: h.close()


@pytest.mark.parametrize('value', [-1, 5, 1.0, True])
def test_shelf_invalid_config(value):
    with pytest.raises(ValueError): Config(evidence_shelf_size=value)


@pytest.mark.parametrize('field', ['disclose_retriever', 'compiled_query_cache', 'recall_navigation', 'centered_recall'])
def test_flag_contracts(field):
    with pytest.raises(ValueError): Config(**{field: 1})


def test_find_mode_rejects_string():
    with pytest.raises(ContractError): validate('find', {'ref':'d1','text':'a','ignore_case':'yes'})
