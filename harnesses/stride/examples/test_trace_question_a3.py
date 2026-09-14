"""Synthetic localhost only: capture identity, persisted attempts, failure stop, export."""
import json
import sqlite3
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

import trace_question_a3 as trace
from stride_search.cpu_index import SQLiteFTS5
from stride_search.fixtures import native
from stride_search.experiment import source_hashes

def ledger(path, cap=100, used=29):
    c=sqlite3.connect(path)
    c.executescript('CREATE TABLE budget(cap INTEGER NOT NULL); CREATE TABLE requests(id INTEGER PRIMARY KEY,run TEXT,role TEXT,status TEXT,http_status INTEGER,usage TEXT);')
    c.execute('INSERT INTO budget VALUES (?)',(cap,))
    c.executemany('INSERT INTO requests(run,role,status) VALUES (?,?,?)',[('historical-synthetic','policy','done')]*used)
    c.commit();c.close()

def test_missing_ledger_never_created(tmp_path):
    p=tmp_path/'missing.sqlite'
    with pytest.raises(sqlite3.OperationalError): trace.Budget(p,'new')
    assert not p.exists()

def test_global_and_per_episode_budget(tmp_path):
    p=tmp_path/'budget.sqlite';ledger(p,cap=32,used=0)
    b=trace.Budget(p,'episode')
    for _ in range(32):b.take()
    with pytest.raises(trace.ContractError): b.take()
    b.close()
    with pytest.raises(ValueError): trace.Budget(p,'second-episode')
    c=sqlite3.connect(p)
    assert c.execute('SELECT count(*) FROM requests').fetchone()[0]==32
    assert c.execute("SELECT count(*) FROM requests WHERE status='unknown'").fetchone()[0]==32
    c.close()

def test_insufficient_allowance_has_no_charge(tmp_path):
    p=tmp_path/'budget.sqlite';ledger(p,100,69)
    before=p.read_bytes()
    with pytest.raises(ValueError):trace.Budget(p,'new')
    assert p.read_bytes()==before

@pytest.mark.parametrize('mode',['success','http429','truncated','identity','secret_echo'])
def test_loopback_episode_and_export(tmp_path,monkeypatch,mode):
    monkeypatch.setenv('NO_PROXY','127.0.0.1,localhost,::1')
    budget=tmp_path/'budget.sqlite';ledger(budget)
    qpath=tmp_path/'question.json'
    trace.save(qpath,{'qid':'synthetic-72','question':'SYNTHETIC ONLY: Who directs Lumen?'})
    index_path=tmp_path/'synthetic.sqlite';c=sqlite3.connect(index_path)
    c.executescript("CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE docs(docid TEXT,content TEXT,url TEXT); CREATE VIRTUAL TABLE search USING fts5(content,content='docs',content_rowid='rowid',tokenize='porter unicode61');")
    c.execute('INSERT INTO metadata VALUES (?,?)',('identity',json.dumps({'complete':True,'documents':1})))
    c.execute('INSERT INTO docs VALUES (?,?,?)',('fixture','Lumen is directed by Ada Rowan.','https://fixture.invalid/lumen'))
    c.execute("INSERT INTO search(search) VALUES ('rebuild')");c.commit();c.close()
    before=index_path.read_bytes()
    index=SQLiteFTS5(index_path,index_id='synthetic');identity=index.identity;index.close()
    queue=[native(('search',{'queries':['Lumen'],'top_k':1})),native(('read',{'ref':'d1'})),native(('finish',{'answer':'Ada Rowan','refs':['e1']}))]
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if mode=='http429':
                self.send_response(429);self.end_headers();self.wfile.write(b'{"error":"synthetic quota"}');return
            raw=queue.pop(0);raw['model']='glm-5.2'
            if mode=='truncated':raw['choices'][0]['finish_reason']='length'
            if mode=='identity':raw['model']='changed-model'
            if mode=='secret_echo':raw['choices'][0]['message']['content']='SYNTHETIC_SECRET_FOR_TEST_ONLY'
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(raw).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}/v1'
    monkeypatch.setenv('ESR_API_KEY','SYNTHETIC_SECRET_FOR_TEST_ONLY');monkeypatch.setenv('ESR_BASE_URL',base)
    root=tmp_path/'episode-output';repo=Path(trace.__file__).resolve().parents[3]
    # The synthetic fixture follows its checkout; production remains release-pinned.
    monkeypatch.setattr(trace, 'RELEASE', subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip())
    plan={'qid':'synthetic-72','worktree':str(repo),'source_hashes':source_hashes(),'collector_sha256':trace.sha(trace.__file__),
          'config':trace.config().to_dict(),'base_url':base,'question_path':str(qpath),'question_sha256':trace.sha(qpath),
          'output':str(root),'budget_path':str(budget),'index_path':str(index_path),'index_id':'synthetic','index_identity':identity}
    plan_path=tmp_path/'plan.json';trace.save(plan_path,plan)
    try:
        trace.run(plan_path)
        result=json.loads((root/'result.json').read_text(encoding='utf-8'))
        expected={'success':'submitted','http429':'http_error','truncated':'incomplete_response','identity':'model_identity_changed','secret_echo':'credential_echo'}[mode]
        assert result['terminal']['outcome']==expected
        assert len(received)==(3 if mode=='success' else 1)
        assert result['http_attempts']==len(received)
        assert all(r['temperature']==0 for r in received)
        assert 'retriever_capabilities' in received[0]['messages'][-1]['content']
        checks=json.loads((root/'INTEGRITY_CHECKS.json').read_text(encoding='utf-8'))
        assert checks['all_json_equivalent']
        assert all(r['canonical_serialization_matches_sent_body'] for r in checks['request_correspondence'])
        assert index_path.read_bytes()==before
        c=sqlite3.connect(budget);assert c.execute('SELECT count(*) FROM requests').fetchone()[0]==29+len(received);c.close()
        for path in root.rglob('*'):
            if path.is_file():assert b'SYNTHETIC_SECRET_FOR_TEST_ONLY' not in path.read_bytes()
        with pytest.raises(FileExistsError):trace.run(plan_path)
    finally:
        server.shutdown();server.server_close();thread.join()
