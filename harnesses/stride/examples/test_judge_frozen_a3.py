import importlib.util
import json
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import pytest

from judge_frozen_a3 import JudgeBudget, validate_response
from trace_question_a3 import CaptureOpener
from test_trace_question_a3 import ledger


@pytest.mark.parametrize('mode', ['success', 'length', 'identity', 'string_boolean'])
def test_one_local_judge_attempt_and_strict_result(tmp_path, monkeypatch, mode):
    monkeypatch.setenv('NO_PROXY', 'localhost,127.0.0.1')
    monkeypatch.setenv('ESR_API_KEY', 'SYNTHETIC_JUDGE_SECRET')
    path = Path(__file__).resolve().parents[3] / 'src/esr_grpo/judge.py'
    spec = importlib.util.spec_from_file_location('synthetic_project_judge', path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    parsed = {'correct': 'false' if mode == 'string_boolean' else True, 'extracted_answer': 'Ada', 'rationale': 'Same name'}
    raw = {'model': 'changed' if mode == 'identity' else 'glm-5.2', 'choices': [
        {'finish_reason': 'length' if mode == 'length' else 'stop', 'message': {'role': 'assistant', 'content': json.dumps(parsed)}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(raw).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}/v1'
    budget_path = tmp_path / 'synthetic.sqlite'; ledger(budget_path, cap=1000, used=59)
    budget = JudgeBudget(budget_path, 'synthetic-judge', 1)
    capture = CaptureOpener(tmp_path, budget, 'SYNTHETIC_JUDGE_SECRET', base + '/chat/completions')
    try:
        judge = module.OpenAICompatibleJudge(base, 'EB-GLM-5.2', api_key_env='ESR_API_KEY')
        with patch.object(module.urllib.request, 'urlopen', capture.open):
            result = judge.judge('Synthetic question', 'Ada', 'Ada')
        if mode == 'success':
            validate_response(raw, parsed); assert result.correct
        else:
            with pytest.raises(ValueError): validate_response(raw, parsed)
        assert len(received) == 1
        assert received[0]['temperature'] == 0 and received[0]['top_p'] == 1
        assert received[0]['max_tokens'] == 2048
        assert budget.db.execute("SELECT count(*) FROM requests WHERE role='judge'").fetchone()[0] == 1
        with pytest.raises(ValueError): budget.take()
        assert budget.snapshot()['used'] == 60
        for f in tmp_path.glob('http/**/*'):
            if f.is_file(): assert b'SYNTHETIC_JUDGE_SECRET' not in f.read_bytes()
    finally:
        budget.close(); server.shutdown(); server.server_close(); worker.join()
