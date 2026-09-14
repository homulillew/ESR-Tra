"""Real loopback POST roundtrips for recovery; never contacts a model service."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from stride_search import Config, Harness
from stride_search.contract import canonical
from stride_search.fixtures import native, smoke_corpus
from stride_search.providers import AnthropicModel, HTTP, LocalCorpus, OpenAIModel
from test_engine import A, F, R, S
from test_recovery_v2 import note


def anthropic(raw):
    message = raw['choices'][0]['message']
    blocks = [{'type': 'thinking', 'thinking': 'LOCAL_PRIVATE_SYNTHETIC_902', 'signature': 'fixture-signature'}]
    if message.get('content'):
        blocks.append({'type': 'text', 'text': message['content']})
    for call in message.get('tool_calls', []):
        blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'],
                       'input': json.loads(call['function']['arguments'])})
    return {'role': 'assistant', 'model': 'fixture', 'content': blocks,
            'stop_reason': 'tool_use' if message.get('tool_calls') else 'end_turn',
            'usage': {'input_tokens': 100, 'output_tokens': 20}}


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
@pytest.mark.parametrize('case', ['soft_note', 'prose', 'capacity'])
def test_recovery_native_http_roundtrip(provider, case, tmp_path):
    corpus = smoke_corpus()
    config = Config(max_model_calls=3)
    if case == 'soft_note':
        replies = [S, R, native(note(), ('finish', {'answer': 'Ada Rowan', 'refs': ['e1']}))]
    elif case == 'prose':
        replies = [S, R, native(content='RAW_REPAIR_778 "Ada Rowan"', finish_reason='stop'), F]
        config = Config(max_model_calls=4)
    else:
        corpus = LocalCorpus([{'docid': 'large', 'title': 'LongArchive', 'content': 'X' * 26000}])
        config = Config(max_model_calls=3, context_limit=28000, response_reserve=2048)
        replies = [native(('search', {'queries': ['LongArchive'], 'top_k': 1})),
                   native(*[('read', {'ref': 'd1', 'start': i * 6000, 'length': 6000}) for i in range(4)]), A]
    received = []
    queue = deepcopy(replies)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append(body)
            raw = queue.pop(0)
            payload = anthropic(raw) if provider == 'anthropic' else raw
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    h = Harness('Who was first?', corpus, path=tmp_path/'episode.sqlite', config=config)
    cls = AnthropicModel if provider == 'anthropic' else OpenAIModel
    model = cls(f'http://127.0.0.1:{server.server_port}/v1', 'fixture', revision='offline', http=HTTP(allow_network=True))
    try:
        terminal = h.run(model)
        assert terminal['outcome'] == ('abstained' if case == 'capacity' else 'submitted')
        assert len(received) == len(replies) == h.model_calls and not queue
        h.archive.verify()
        if case == 'prose':
            control = canonical(received[-1]['messages'][-1])
            assert 'RAW_REPAIR_778' in control
            # Native thinking can occur in earlier history but not the repair payload.
            assert 'LOCAL_PRIVATE_SYNTHETIC_902' not in control
        if case == 'capacity':
            assert 0 < len(h.exposed) < 4
            assert h.archive.report()['recovery_events']['result_withheld'] > 0
        if provider == 'anthropic':
            for request in received[1:]:
                messages = request['messages']
                for i, m in enumerate(messages):
                    expected = [b['id'] for b in m['content'] if b['type'] == 'tool_use']
                    if expected:
                        actual = [b['tool_use_id'] for b in messages[i+1]['content'] if b['type'] == 'tool_result']
                        assert expected == actual
    finally:
        h.close()
        server.shutdown(); server.server_close(); thread.join(timeout=2)
