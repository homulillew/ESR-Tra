from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import MemoryRetriever, hf_counter
from esr_harness_v3.state import claim_sources
from .conftest import DOCS, add, send, source


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('renamed', [False, True])
def test_consistent_document_renaming_and_order_preserve_selected_content(reverse, renamed):
    docs = [{'docid': 'z' if renamed else 'A', 'title': 'Same title', 'content': 'Record 2020: Mira.'},
            {'docid': 'a' if renamed else 'B', 'title': 'Same title', 'content': 'Record 2021: Orin.'}]
    if reverse:
        docs.reverse()
    h = Harness('Who in 2020?', MemoryRetriever(docs), config=Config(require_sources=True))
    try:
        hits = send(h, ('search', {'query': 'Record'}))[0]['hits']
        selected = next(hit for hit in hits if '2020' in hit['snippet'])
        opened = send(h, ('open_page', {'ref': selected['ref']}))[0]['observation']
        result = send(h, ('submit_answer', {'answer': 'Mira', 'refs': [opened['observation']]}))[0]
        assert result['ok'] and '2020: Mira' in h.state['observations'][result['terminal']['basis']['sources'][0]]['text']
        assert h.state['documents'][opened['document']]['backend_id'] == selected['docid']
    finally:
        h.close()


def test_legal_handle_with_wrong_source_is_not_semantic_success():
    h = Harness('Who won in 2014?', MemoryRetriever(DOCS), config=Config(require_sources=True))
    try:
        hits = send(h, ('search', {'query': 'tournament'}))[0]['hits']
        wrong = next(hit for hit in hits if hit['docid'] == 'B')
        opened = send(h, ('open_page', {'ref': wrong['ref']}))[0]['observation']
        result = send(h, ('submit_answer', {'answer': 'Mira', 'refs': ['this']}))[0]
        assert result['ok']  # The structural contract cannot decide semantic support.
        cited = h.state['observations'][result['terminal']['basis']['sources'][0]]
        assert h.state['documents'][cited['document']]['backend_id'] == 'B'
        assert '2014' not in cited['text'] and result['terminal']['audit_status'] == 'unverified'
    finally:
        h.close()


def test_source_removal_invalidates_transitive_dependents_but_keeps_raw_history():
    h = Harness('Q', MemoryRetriever(DOCS))
    try:
        first = source(h)
        second = send(h, ('open_page', {'ref': 'd2'}))[0]['observation']['observation']
        c1 = add(h, refs=[first, second])
        c2 = add(h, 'Derived', refs=[c1])
        c3 = add(h, 'Further', refs=[c2])
        independent = add(h, 'Independent', refs=[first])
        before = deepcopy(h.state['observations'])
        # EDIT deliberately requires finding + refs together, even when the text stays identical.
        assert send(h, ('update_state', {'revise': [{'claim': c1, 'finding': 'A fact', 'refs': [first]}]}))[0]['ok']
        assert {c2, c3} <= set(h.state['invalid']) and independent not in h.state['invalid']
        assert h.state['observations'] == before
        assert claim_sources(h.state, independent, 1) == [first]
    finally:
        h.close()


def test_local_tokenizer_identity_tracks_vocabulary_and_template(monkeypatch, tmp_path):
    class Tokenizer:
        chat_template = 'template-A'
        special_tokens_map = {'bos_token': '<s>'}
        def get_vocab(self):
            return {'<s>': 0, 'word': 1}
        def apply_chat_template(self, messages, **kwargs):
            return [0, 1]
    tok = Tokenizer()
    def load(path, **kwargs):
        assert kwargs == {'local_files_only': True, 'trust_remote_code': False}
        return tok
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=load)))
    count, unit = hf_counter('fixture-path')
    assert count([], []) == 2 and unit == 'local_chat_template_tokens'
    h = Harness('Q', MemoryRetriever(DOCS), ledger=tmp_path/'tokens.sqlite', counter=count, counter_name=unit)
    h.close()
    tok.chat_template = 'template-B'
    changed, _ = hf_counter('fixture-path')
    with pytest.raises(ContractError, match='must match'):
        Harness('Q', MemoryRetriever(DOCS), ledger=tmp_path/'tokens.sqlite', counter=changed, counter_name=unit, resume=True)


@pytest.mark.parametrize('nested', [None, ['invalid document']])
def test_bad_document_envelope_does_not_partially_commit_or_crash(nested):
    class Retriever(MemoryRetriever):
        def get_document(self, docid):
            return {'docid': docid, 'document': nested}
    h = Harness('Q', Retriever(DOCS))
    try:
        send(h, ('search', {'query': 'tournament'}))
        results = send(h, [('open_page', {'ref': 'd1'}), ('submit_answer', {'answer': 'A'})])
        assert results[0]['code'] == 'retrieval_error' and not results[1]['executed']
        assert not h.state['observations'] and h.terminal['outcome'] == 'retrieval_error'
    finally:
        h.close()
