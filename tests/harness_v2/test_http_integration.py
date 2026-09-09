"""Real localhost HTTP plumbing, with deterministic fake policy/auditor services."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from esr_harness.v2 import cli
from esr_harness.v2.demo import DemoAuditor, DemoPolicy
from esr_harness.v2.runner import replay


class Counter:
    identity = {"fixture": "http-test-counter"}
    def __init__(self, *args): pass
    def __call__(self, messages, thinking): return 10


def test_complete_cli_over_http_without_label_leakage(tmp_path, monkeypatch):
    text = "Alex won the Lake Cup in 2010. Taylor won the Lake Cup in 2008."
    policy, requests = DemoPolicy(), []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body))
            if self.path == "/retrieve":
                result = {"result": [[{"docid": "lake", "score": 1.0,
                                       "document": {"contents": text, "title": "Lake Cup"}}]]}
            elif self.path == "/get_doc":
                result = {"docid": "lake", "document": {"contents": text, "title": "Lake Cup"}}
            elif self.path == "/get_doc_chunks":
                result = {"chunks": [{"text": text, "chunk_index": 0}]}
            elif self.path == "/v1/chat/completions":
                if body["messages"][0]["content"].startswith("Audit an answer"):
                    assert len(body["messages"]) == 2
                    payload = json.loads(body["messages"][1]["content"])
                    answer = DemoAuditor().audit(payload["question"], payload, payload["observations"])
                    content = json.dumps(answer)
                else:
                    content = policy.complete(body["messages"])
                result = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
            else:
                self.send_error(404)
                return
            encoded = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    dataset, store = tmp_path / "qa.jsonl", tmp_path / "episode.sqlite"
    dataset.write_text(json.dumps({"query_id": "test", "query": "Who won the Lake Cup two years before Alex?",
                                   "answer": "GOLD_CANARY_DO_NOT_LEAK", "gold_docids": ["ORACLE_DOC_CANARY"]}) + "\n")
    monkeypatch.setattr(cli, "HFTokenCounter", Counter)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        exit_code = cli.main(["run", "--dataset", str(dataset), "--qid", "test", "--mode", "esr",
                              "--audit-mode", "hard", "--policy-url", base + "/v1", "--model", "fixture",
                              "--tokenizer", "fake-for-http-test-only", "--retrieval-url", base,
                              "--store", str(store)])
        assert exit_code == 0
        restored = replay(str(store))
        assert restored.terminal["answer"] == "Taylor" and restored.attempts == 7
        assert "GOLD_CANARY" not in json.dumps(requests)
        assert "ORACLE_DOC_CANARY" not in json.dumps(restored.ledger.events())
        summary = json.loads(store.with_suffix(".summary.json").read_text())
        assert summary["usage"]["completion_tokens"] == 45  # seven policy + two audit calls
        assert summary["usage"]["unknown_usage_requests"] == 0
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
