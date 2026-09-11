"""Real loopback HTTP, synthetic content, no paid model requests."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from esr_harness_v3 import Config, Harness
from esr_harness_v3.adapters import EchoRetriever, OpenAICompatible, run_episode
from esr_harness_v3.protocol import canonical
from esr_harness_v3.store import Ledger


@contextmanager
def server_fixture(mode):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        policy_calls = 0
        def log_message(self, *args):
            pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append({'path': self.path, 'body': request})
            code = 200
            if self.path.endswith('chat/completions'):
                Handler.policy_calls += 1
                n = Handler.policy_calls
                actions = {1: [('search', {'query': 'record A'}), ('search', {'query': 'record B'})],
                           2: [('open_page', {'ref': 'd1'}), ('open_page', {'ref': 'd2'})],
                           3: [('update_state', {'add': [{'requirement': 'Director', 'finding': 'Mira', 'refs': ['o1']}]}),
                               ('submit_answer', {'answer': 'Mira', 'refs': ['o1']})]}[n]
                response = {'model': 'loopback-model', 'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
                            'choices': [{'finish_reason': 'length' if mode == 'truncated' else 'tool_calls',
                                         'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': f'n{n}_{i}', 'type': 'function', 'function': {'name': name, 'arguments': canonical(args)}}
                    for i, (name, args) in enumerate(actions)]}}]}
                if mode == 'policy_401':
                    code, response = 401, {'error': 'local-test-key must not reach ledger'}
            elif self.path == '/retrieve':
                docid = request['queries'][0][-1]
                response = {'result': [[{'docid': docid, 'title': 'Similar record', 'content': f'Record {docid}'}]]}
                if mode == 'backend_429':
                    code, response = 429, {'error': 'local-test-key must not reach ledger'}
            else:
                response = {'docid': request['docid'], 'title': 'Similar record', 'content': 'Director Mira.'}
            payload = canonical(response).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize('mode', ['success', 'backend_429', 'policy_401', 'truncated'])
def test_http_native_groups_and_failures_are_durable(tmp_path, mode):
    path = tmp_path / 'native.sqlite'
    with server_fixture(mode) as (base, seen):
        h = Harness('Who was director?', EchoRetriever(base, index_fingerprint='synthetic-1'), ledger=path,
                    config=Config(max_model_calls=5, require_sources=True))
        try:
            terminal = run_episode(h, OpenAICompatible(base + '/v1', 'loopback-model', api_key='local-test-key'))
            exported = h.ledger.export()
            assert 'local-test-key' not in canonical(exported)
            policy = [r['body'] for r in seen if r['path'].endswith('chat/completions')]
            if mode == 'success':
                assert terminal['answer'] == 'Mira' and h.state['backend_calls'] == 4
                assert h.state['actions'] == 6 and len(policy) == 3
                for i in (1, 2):
                    receipts = {m['tool_call_id'] for m in policy[i]['messages'] if m['role'] == 'tool'}
                    assert {f'n{i}_0', f'n{i}_1'} <= receipts
                assert json.loads(policy[2]['messages'][-1]['content'].split('\n', 1)[1])['this'] is None
                assert h.state['usage'] == {'input_tokens': 30, 'output_tokens': 15, 'unknown_calls': 0}
            else:
                assert len(policy) == 1 and not terminal['answer']
                assert terminal['outcome'] == ('incomplete_response' if mode == 'truncated' else 'service_error')
                if mode == 'backend_429':
                    batches = [e['payload']['receipts'] for e in exported['events'] if e['kind'] == 'batch_complete']
                    assert len(batches[0]) == 2 and not batches[0][1]['executed']
                    assert h.state['backend_calls'] == 1
                if mode == 'policy_401':
                    assert h.state['usage']['unknown_calls'] == 1
        finally:
            h.close()
        before = len(seen)
        replay = Ledger(path, readonly=True)
        try:
            assert replay.export()['state']['terminal'] == terminal
            assert len(seen) == before
        finally:
            replay.close()
