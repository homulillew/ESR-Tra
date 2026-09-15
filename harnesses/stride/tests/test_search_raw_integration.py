"""Real loopback CLI/SQLite checks using synthetic documents only."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from stride_search.archive import Archive
from stride_search.cli import main
from stride_search.contract import text_hash
from stride_search.fixtures import native
from test_cpu_index import make_index
from test_recovery_http import anthropic
from test_workflow_live import live


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
@pytest.mark.parametrize('case', ['automatic', 'same_response_guess', 'baseline'])
def test_search_raw_cli_delivery_binding_and_replay(provider, case, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')
    monkeypatch.delenv('STRIDE_API_KEY', raising=False)
    passage = 'Lumen Observatory opened in 2012. Its first director was Ada Rowan.'
    index = make_index(tmp_path / 'index.sqlite', docs=[
        ('lumen', passage, 'https://synthetic.example/lumen'),
        ('other', 'Unrelated synthetic archive.', 'https://synthetic.example/other'),
    ])
    index_bytes = index.read_bytes()
    question = tmp_path / 'question.txt'
    question.write_text('Who was the first director of Lumen Observatory?', encoding='utf-8')
    search = ('search', {'queries': ['Lumen'], 'top_k': 1})
    finish = ('finish', {'answer': 'Ada Rowan', 'refs': ['e1']})
    if case == 'automatic':
        replies = [native(search), native(finish)]
    elif case == 'same_response_guess':
        replies = [native(search, finish), native(finish)]
    else:
        replies = [native(search), native(finish), native(('read', {'ref': 'd1'})), native(finish)]
    protocol = 'baseline' if case == 'baseline' else 'search-raw-window-v1'
    queue = deepcopy(replies)
    requests, response_bodies = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append(self.rfile.read(int(self.headers['Content-Length'])))
            raw = queue.pop(0)
            payload = anthropic(raw) if provider == 'anthropic' else raw
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            response_bodies.append(body)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    db = tmp_path / 'episode.sqlite'
    try:
        assert main(['run', '--allow-network', '--accept-counter-estimate',
            '--base-url', f'http://127.0.0.1:{server.server_port}/v1',
            '--model', 'fixture', '--model-revision', 'synthetic', '--model-api', provider,
            '--sqlite-index', str(index), '--index-id', 'synthetic-lumen', '--counter', 'utf8_bytes',
            '--question-file', str(question), '--db', str(db), '--max-model-calls', '5',
            '--context-limit', '100000', '--response-reserve', '8192',
            '--decision-protocol', protocol]) == 0
        report = json.loads(capsys.readouterr().out)
        assert not queue and len(requests) == len(replies)
        assert report['terminal']['outcome'] == 'submitted'
        assert report['terminal']['answer'] == 'Ada Rowan'
        assert report['terminal']['refs'] == ['e1']
        assert report['backend_attempts'] == 2
        assert index.read_bytes() == index_bytes
        archive = Archive(db, readonly=True)
        try:
            events = list(archive.events())
            assert archive.verify()['head'] == report['head']
            assert [archive.load_request(e['payload']['request']) for e in events
                    if e['kind'] == 'model_request'] == [json.loads(x) for x in requests]
            assert [archive.json(e['payload']['raw']) for e in events
                    if e['kind'] == 'model_response'] == [json.loads(x) for x in response_bodies]
            evidence = archive.evidence('e1')
            assert evidence['text'] == passage
            assert evidence['text'] == archive.get(evidence['snapshot'])[evidence['start']:evidence['end']]
            assert evidence['sha256'] == text_hash(evidence['text'])
            assert evidence['end'] - evidence['start'] <= 3000
            acks = [e['payload'] for e in events if e['kind'] == 'delivery_ack']
            assert acks[0]['evidence'] == []
            first_delivery = next(a['round'] for a in acks if 'e1' in a['evidence'])
            assert first_delivery == (4 if case == 'baseline' else 2)
            # The full original passage is present in the actual receiving request.
            assert passage in json.dumps(json.loads(requests[first_delivery - 1]), ensure_ascii=False)
            actions = [e['payload'] for e in events if e['kind'] == 'action_result']
            read_actions = [a for a in actions if a['tool'] == 'read']
            assert len(read_actions) == (1 if case == 'baseline' else 0)
            attempts = [e for e in events if e['kind'] == 'search_raw_attempt']
            assert len(attempts) == (0 if case == 'baseline' else 1)
            if case != 'automatic':
                denied = [a for a in actions if a['tool'] == 'finish' and not a['result']['ok']]
                assert len(denied) == 1
                assert denied[0]['result']['code'] == 'unreceived_reference'
            if case != 'baseline':
                result = next(a['result'] for a in actions if a['tool'] == 'search')
                window = result['raw_windows'][0]
                assert window['kind'] == 'harness_acquired_raw_window'
                assert window['evidence'] == evidence
                assert window['previously_received'] is False
            assert archive.report() == report
        finally:
            archive.close()
        # Exercise the production exporter against actual loopback body bytes.
        # No timestamp capture was installed; null explicitly means unavailable.
        (tmp_path / 'events-timed.jsonl').write_text(''.join(
            json.dumps({'seq': e['seq'], 'utc': None}) + '\n' for e in events), encoding='utf-8')
        for number, (request, response) in enumerate(zip(requests, response_bodies), 1):
            folder = tmp_path / 'http' / f'{number:03d}'
            folder.mkdir(parents=True)
            (folder / 'request.body').write_bytes(request)
            (folder / 'response.body').write_bytes(response)
        live.export(tmp_path)
        checks = json.loads((tmp_path / 'INTEGRITY_CHECKS.json').read_text(encoding='utf-8'))
        assert checks['all_json_equivalent']
        assert checks['archive']['head'] == report['head']
        exported_events = [json.loads(line) for line in
                           (tmp_path / 'trajectory.jsonl').read_text(encoding='utf-8').splitlines()]
        assert [{k: v for k, v in e.items() if k != 'utc'} for e in exported_events] == events
        interaction = (tmp_path / 'FULL_INTERACTION.md').read_text(encoding='utf-8')
        assert passage in interaction
        for number, (request, response) in enumerate(zip(requests, response_bodies), 1):
            assert (tmp_path / 'http' / f'{number:03d}' / 'request.body').read_bytes() == request
            assert (tmp_path / 'http' / f'{number:03d}' / 'response.body').read_bytes() == response
        assert main(['replay', '--db', str(db)]) == 0
        exported = capsys.readouterr().out
        (tmp_path / 'report.json').write_text(exported, encoding='utf-8')
        assert json.loads(exported) == report
        assert main(['diagnose', '--db', str(db)]) == 0
        diagnostic = json.loads(capsys.readouterr().out)
        assert diagnostic['delivered_refs'] == ['e1']
        assert diagnostic['formal_correct'] is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
