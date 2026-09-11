from copy import deepcopy
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sqlite3
import threading
import pytest

from esr_harness_v3 import Config, ContractError, Harness
from esr_harness_v3.adapters import EchoRetriever, MemoryRetriever, OpenAICompatible, run_episode
from esr_harness_v3.cli import main, smoke
from esr_harness_v3.protocol import canonical
from esr_harness_v3.store import Ledger
from esr_harness_v3.training import training_export
from .conftest import DOCS, AuditFixture, add, send, source


def test_persistent_smoke_and_readonly_replay(tmp_path):
    path = tmp_path / 'run.sqlite'
    result = smoke(path)
    ledger = Ledger(path, readonly=True)
    assert ledger.export()['state']['terminal']['answer'] == 'Mira Vale'
    assert ledger.seq == result['event_count']
    with pytest.raises(ContractError):
        ledger.append('forbidden', {})
    ledger.close()


def test_existing_ledger_not_overwritten(tmp_path):
    path = tmp_path / 'run.sqlite'
    h = Harness('Q', MemoryRetriever(DOCS), ledger=path)
    h.close()
    with pytest.raises(ContractError, match='new ledger'):
        Harness('Q', MemoryRetriever(DOCS), ledger=path)


def test_resume_completed_batch(tmp_path):
    path = tmp_path / 'run.sqlite'
    h = Harness('Q', MemoryRetriever(DOCS), ledger=path)
    source(h); add(h)
    old = h.state['claims']
    h.close()
    resumed = Harness('Q', MemoryRetriever(DOCS), ledger=path, resume=True)
    assert resumed.state['claims'] == old
    assert send(resumed, ('submit_answer', {'answer': 'A', 'refs': ['c1']}))[0]['ok']
    resumed.close()


def test_resume_interrupted_request_never_resends(tmp_path):
    path = tmp_path / 'run.sqlite'
    h = Harness('Q', MemoryRetriever(DOCS), ledger=path)
    h.begin(); h.close()
    resumed = Harness('Q', MemoryRetriever(DOCS), ledger=path, resume=True)
    assert resumed.terminal['outcome'] == 'interrupted'
    assert resumed.state['model_calls'] == 1
    resumed.close()


def test_hash_chain_detects_tampering(tmp_path):
    path = tmp_path / 'run.sqlite'
    smoke(path)
    db = sqlite3.connect(path)
    db.execute("UPDATE v3_events SET body='{}' WHERE seq=2"); db.commit(); db.close()
    with pytest.raises(ContractError, match='Hash/sequence'):
        Ledger(path, readonly=True)


def test_optimistic_writer_does_not_overwrite(tmp_path):
    path = tmp_path / 'run.sqlite'
    first = Harness('Q', MemoryRetriever(DOCS), ledger=path)
    second = Harness('Q', MemoryRetriever(DOCS), ledger=path, resume=True)
    send(first, ('update_state', {'note': 'one'}))
    with pytest.raises(ContractError, match='Ledger changed'):
        second.begin()
    first.close(); second.close()


def test_resume_different_index_rejected(tmp_path):
    path = tmp_path / 'run.sqlite'
    h = Harness('Q', MemoryRetriever(DOCS), ledger=path); h.close()
    with pytest.raises(ContractError, match='must match'):
        Harness('Q', MemoryRetriever(DOCS[:1]), ledger=path, resume=True)


def test_old_ledger_not_silently_migrated(tmp_path):
    path = tmp_path / 'v2.sqlite'
    db = sqlite3.connect(path); db.execute('CREATE TABLE events (id INTEGER)'); db.close()
    with pytest.raises(ContractError, match='Missing v3'):
        Ledger(path, readonly=True)


def test_capacity_failure_does_not_claim_delivery():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(context_limit=1000, output_reserve=50))
    with pytest.raises(ContractError, match='minimum legal'):
        h.begin()
    assert h.state['model_calls'] == 0 and not h.state['exposed']
    h.close()


def test_compaction_preserves_native_pairs_and_frozen_alias():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(context_limit=16000, output_reserve=500, max_model_calls=50))
    oid = source(h)
    for i in range(20):
        send(h, ('update_state', {'note': f'note {i} ' + 'context ' * 40}))
    decision = h.begin()
    assert h.state['segment'] > 0
    assert decision.binding['this'] == oid
    waiting = set()
    for message in decision.payload['messages']:
        if message['role'] == 'assistant' and message.get('tool_calls'):
            assert not waiting
            waiting = {c['id'] for c in message['tool_calls']}
        elif message['role'] == 'tool':
            assert message['tool_call_id'] in waiting
            waiting.remove(message['tool_call_id'])
    assert not waiting
    h.close()


def test_full_batch_not_shrunk_to_fabricate_single_this():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(context_limit=16000, output_reserve=500, max_model_calls=50))
    send(h, ('search', {'query': 'tournament'}))
    send(h, [('open_page', {'ref': 'd1'}), ('open_page', {'ref': 'd2'})])
    for i in range(12):
        send(h, ('update_state', {'note': str(i) + 'x' * 800}))
    assert h.begin().binding['this'] is None
    h.close()


def test_source_requirement_is_explicit():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(require_sources=True))
    result = send(h, ('submit_answer', {'answer': 'A'}))[0]
    assert result['code'] == 'sources_required'
    assert send(h, ('submit_answer', {'decision': 'abstain', 'reason': 'No source'}))[0]['ok']
    h.close()


def test_last_policy_can_submit_without_prior_update():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(max_model_calls=3))
    source(h)
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))[0]['ok']
    assert h.state['model_calls'] == 3
    h.close()


def test_budget_does_not_salvage_draft():
    h = Harness('Q', MemoryRetriever(DOCS), config=Config(max_model_calls=1))
    send(h, ('update_state', {'draft': {'answer': 'A', 'refs': []}}))
    with pytest.raises(ContractError):
        h.begin()
    assert h.terminal['answer'] == '' and h.terminal['draft']['answer'] == 'A'
    h.close()


def test_bad_refs_not_fuzzy_fixed(h):
    source(h)
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['o99']}))[0]['code'] == 'unexposed_reference'
    assert send(h, ('submit_answer', {'answer': 'A', 'refs': ['c1']}))[0]['code'] == 'unpublished_claim'
    assert h.terminal is None


def test_search_cache_is_not_free_policy_call(h):
    send(h, ('search', {'query': 'tournament'}))
    r = send(h, ('search', {'query': 'tournament'}))[0]
    assert r['cache_source'] and h.state['backend_calls'] == 1
    assert h.state['model_calls'] == 2


def test_training_export_refuses_fabricated_alignment(h):
    source(h)
    send(h, ('submit_answer', {'answer': 'A', 'refs': ['this']}))
    exported = training_export(h.ledger)
    assert not exported['rl_ready']
    assert exported['records'][-1]['binding']['this'] == 'o1'
    with pytest.raises(ContractError, match='Exact sampler'):
        training_export(h.ledger, require_rl=True)


def test_training_accepts_explicit_exact_sampler_fields(h):
    d = h.begin()
    msg = {'role': 'assistant', 'tool_calls': [{'id': 'final', 'type': 'function', 'function': {
        'name': 'submit_answer', 'arguments': '{"answer":"A"}'}}]}
    sample = {'token_ids': [1, 2, 3], 'old_logprobs': [-1., -1., -.3],
              'action_spans': [{'tool_call_id': 'final', 'start': 0, 'end': 3}], 'tokenizer_identity': 'fixture'}
    h.respond(d, msg, sampling=sample)
    assert training_export(h.ledger, require_rl=True)['rl_ready']


def test_cli_network_requires_authorization(tmp_path):
    args = ['run', '--question-file', 'x', '--db', str(tmp_path/'x'), '--base-url', 'http://localhost:1/v1',
            '--model', 'x', '--retrieval-url', 'http://localhost:2', '--index-fingerprint', 'x', '--tokenizer', 'x']
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_url_credentials_not_accepted():
    with pytest.raises(ValueError):
        OpenAICompatible('https://user:secret@example.com/v1', 'model')


def test_local_http_end_to_end_native(tmp_path):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        count = 0
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append((self.path, body))
            if self.path == '/retrieve':
                response = {'result': [[{'docid': 'A', 'title': 'Mira', 'content': 'Mira was director.'}]]}
            elif self.path == '/get_doc':
                response = {'docid': 'A', 'content': 'Mira was director.', 'title': 'Mira'}
            else:
                assert self.path == '/v1/chat/completions'
                Handler.count += 1
                name, args = [('search', {'query': 'Mira'}), ('open_page', {'ref': 'd1'}),
                              ('submit_answer', {'answer': 'Mira', 'refs': ['this']})][Handler.count - 1]
                response = {'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': f'call_{Handler.count}', 'type': 'function', 'function': {'name': name, 'arguments': canonical(args)}}]}}],
                    'model': 'local-fixture', 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
            payload = canonical(response).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    h = Harness('Who was director?', EchoRetriever(base, index_fingerprint='fixture'), ledger=tmp_path/'http.sqlite')
    try:
        answer = run_episode(h, OpenAICompatible(base + '/v1', 'fixture', api_key='local-test-key'))
        assert answer['answer'] == 'Mira' and answer['basis']['direct_refs'] == ['o1']
        assert h.state['model_calls'] == 3 and h.state['backend_calls'] == 2
        assert h.state['usage'] == {'input_tokens': 30, 'output_tokens': 15, 'unknown_calls': 0}
        assert 'local-test-key' not in canonical(h.ledger.export())
        request = [body for path, body in seen if path.endswith('chat/completions')][-1]
        assert any(m.get('tool_call_id') == 'call_2' for m in request['messages'])
    finally:
        h.close(); server.shutdown(); server.server_close(); thread.join()


def test_retrieval_url_credentials_rejected():
    with pytest.raises(ValueError):
        EchoRetriever('http://user:secret@localhost', index_fingerprint='x')


def test_write_refuses_legacy_database_without_adding_tables(tmp_path):
    path = tmp_path / 'old.sqlite'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE old_events (id INTEGER)'); db.commit(); db.close()
    with pytest.raises(ContractError, match='legacy'):
        Harness('Q', MemoryRetriever(DOCS), ledger=path)
    db = sqlite3.connect(path)
    assert [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ['old_events']
    db.close()


def test_unresolved_requirement_survives_without_stale_finding(h):
    from esr_harness_v3.context import make_header
    oid = source(h)
    c1 = add(h)
    send(h, ('update_state', {'revise': [{'claim': c1, 'requirement': 'Check the actual 2020 tenure'}]}))
    header, bindings = make_header(h.state, 10, [])
    assert header['unresolved_requirements'][0]['requirement'] == 'Check the actual 2020 tenure'
    assert 'A fact' not in canonical(header)
    assert bindings[c1] == 2
