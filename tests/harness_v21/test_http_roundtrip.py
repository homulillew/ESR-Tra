"""Real localhost HTTP and CLI. Responses are scripted fixtures, not a 4B experiment."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from esr_harness import cli
from esr_harness.demo import DemoPolicy, DemoAuditor
from esr_harness.runner import replay


def test_cli_real_http_roundtrip_and_gold_exclusion(tmp_path,monkeypatch):
    docs={"lake-2010":"Mira won the Lake Cup in 2010.","lake-2008":"Taylor won the Lake Cup in 2008."}
    calls=[]; policy=DemoPolicy()
    class Counter:
        identity={"fixture":"token-counter-not-model"}
        def __init__(self,*a): pass
        def __call__(self,*a): return 10
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length']))); calls.append((self.path,body))
            if self.path=='/retrieve':
                ids=['lake-2010'] if body['queries'][0]=='Mira' else ['lake-2008','lake-2010']
                r={"result":[[{"docid":i,"score":1,"document":{"contents":docs[i]}} for i in ids]]}
            elif self.path=='/get_doc': r={"docid":body['docid'],"document":{"contents":docs[body['docid']]}}
            elif self.path=='/get_doc_chunks': r={"chunks":[{"text":docs[body['docid']]}]}
            elif self.path=='/v1/chat/completions':
                if body['messages'][0]['content'].startswith('Audit the original question'):
                    payload=json.loads(body['messages'][1]['content'])
                    assert len(body['messages'])==2
                    text=json.dumps(DemoAuditor().audit(payload['question'],payload,payload['observations']))
                else: text=policy.complete(body['messages'])
                r={"choices":[{"message":{"content":text},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5}}
            else: self.send_error(404); return
            data=json.dumps(r).encode(); self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    p=tmp_path/'qa.jsonl';store=tmp_path/'run.db'
    p.write_text(json.dumps({"query_id":"test","query":"Who won the same event two years before Mira won in 2010?","answer":"GOLD_ANSWER_CANARY","gold_docids":["SECRET_DOCID_CANARY"]})+'\n')
    monkeypatch.setattr(cli,'HFTokenCounter',Counter);base=f'http://127.0.0.1:{server.server_port}'
    try:
        code=cli.main(['run','--dataset',str(p),'--qid','test','--mode','esr','--audit-mode','hard','--policy-url',base+'/v1','--model','fixture','--tokenizer','fixture','--retrieval-url',base,'--retrieval-revision','fixed-fixture-1','--store',str(store)])
        assert code==0
        h=replay(str(store));assert h.terminal['answer']=='Taylor' and h.exposed=={'o1','o2'}
        assert len([c for c in calls if c[0]=='/retrieve'])==2
        assert 'GOLD_ANSWER_CANARY' not in json.dumps(calls) and 'SECRET_DOCID_CANARY' not in json.dumps(h.ledger.events())
        events=h.ledger.events(); assert len([e for e in events if e['type']=='decision'])==11
        result=json.loads(store.with_suffix('.summary.json').read_text()); assert result['usage']['completion_tokens']==65
        assert result['usage']['unknown_usage_requests']==0
        h.ledger.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
