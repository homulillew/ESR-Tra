"""Actual loopback HTTP + synthetic CPU index. No remote model or BC+ requests."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3
import threading

import pytest

from stride_search import Config
from stride_search.archive import Archive
from stride_search.cli import main
from stride_search.cpu_index import SQLiteFTS5
from stride_search.experiment import make_plan, run_plan
from stride_search.fixtures import ScriptedModel, native
from stride_search.providers import ByteCounter
from test_cpu_index import make_index
from test_recovery_http import anthropic


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_cli_cpu_native_loopback(provider, tmp_path, capsys):
    path = make_index(tmp_path/'cpu.sqlite')
    question = tmp_path/'question.txt'; question.write_text('Who directed Alpha?')
    replies = [native(('search', {'queries':['Alpha'], 'top_k':1})),
               native(('read', {'ref':'d1'})), native(('finish', {'answer':'Mira Stone', 'refs':['e1']}))]
    queue, received = deepcopy(replies), []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            raw = queue.pop(0)
            payload = anthropic(raw) if provider == 'anthropic' else raw
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    db = tmp_path/'episode.sqlite'
    try:
        code = main(['run','--allow-network','--accept-counter-estimate','--base-url',f'http://127.0.0.1:{server.server_port}/v1',
            '--model','fixture','--model-revision','synthetic','--model-api',provider,
            '--sqlite-index',str(path),'--index-id','synthetic-cpu','--counter','utf8_bytes',
            '--question-file',str(question),'--db',str(db),'--max-model-calls','3',
            '--context-limit','100000','--response-reserve','8192'])
        assert code == 0 and len(received) == 3 and not queue
        report = json.loads(capsys.readouterr().out)
        assert report['terminal']['answer'] == 'Mira Stone'
        assert report['backend_attempts'] == 2
        assert 'regex word extraction' in json.dumps(received[0])
        a = Archive(db, readonly=True)
        try:
            requests = [a.load_request(e['payload']['request']) for e in a.events() if e['kind']=='model_request']
            assert requests == received
        finally: a.close()
        assert main(['diagnose','--db',str(db)]) == 0
        diagnostic = json.loads(capsys.readouterr().out)
        assert diagnostic['formal_correct'] is None and diagnostic['delivered_refs'] == ['e1']
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_cpu_factory_closes_after_each_frozen_slot(tmp_path):
    path = make_index(tmp_path/'index.sqlite')
    created = []
    def retrieval():
        item = SQLiteFTS5(path,index_id='synthetic'); created.append(item); return item
    def model():
        return ScriptedModel([native(('finish', {'abstain':True, 'reason':'Synthetic no-reading control'}))])
    first = retrieval(); identity = first.identity; first.close(); created.clear()
    p = make_plan([{'id':'fixture','question':'Q'}],Config(max_model_calls=1),
        {'plain':{'evidence_shelf_size':0},'shelf':{'evidence_shelf_size':3}},
        model_identity=model().identity,retriever_identity=identity,counter_identity=ByteCounter.identity)
    result = run_plan(p,tmp_path/'cohort',model,retrieval,ByteCounter,max_total_model_calls=2)
    assert len(created)==2 and all(r['status']=='abstained' for r in result['rows'])
    for item in created:
        with pytest.raises(sqlite3.ProgrammingError): item.db.execute('SELECT 1')


def test_cpu_authorization_checked_before_index_creation(tmp_path, capsys):
    path = tmp_path/'missing.sqlite'
    code = main(['run','--base-url','http://127.0.0.1:1/v1','--model','x','--model-revision','x',
        '--sqlite-index',str(path),'--index-id','x','--counter','utf8_bytes',
        '--question-file',str(tmp_path/'missing.txt'),'--db',str(tmp_path/'out.sqlite'),
        '--max-model-calls','3','--context-limit','100000','--response-reserve','8192'])
    assert code == 2 and '--allow-network' in capsys.readouterr().err
    assert not path.exists() and not (tmp_path/'out.sqlite').exists()
