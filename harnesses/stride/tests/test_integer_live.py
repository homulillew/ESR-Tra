"""Local capture fixtures for the 4/12 observation bounds; no paid requests."""
import io
from pathlib import Path
import sqlite3
import sys

import pytest
from stride_search import Config, Harness
from stride_search.contract import INTEGER_ANSWER, canonical
from stride_search.fixtures import native, smoke_corpus
from stride_search.providers import HTTP, OpenAIModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/integer_answer'))
from validate_live import Budget, LimitedCapture, observe


@pytest.mark.parametrize('limit', [4, 12])
def test_actual_capture_counts_external_limit_without_terminal(tmp_path, limit):
    path = tmp_path / 'fixture.sqlite'; db = sqlite3.connect(path)
    db.executescript('CREATE TABLE budget(cap INTEGER); INSERT INTO budget VALUES(1000);'
                    'CREATE TABLE requests(id INTEGER PRIMARY KEY,run TEXT,role TEXT,status TEXT,http_status INTEGER,usage TEXT);')
    db.close(); budget = Budget(path, 'local', 16)
    class Response(io.BytesIO): status = 200
    class Transport:
        sent = 0
        def open(self, request, timeout):
            self.sent += 1
            assert budget.snapshot()['this_run'] == self.sent
            # The integer is permitted, but sources_required must still block finish.
            return Response(canonical(native(('finish', {'answer': 47, 'refs': []}))).encode())
    transport = Transport()
    cap = LimitedCapture(tmp_path, budget, '', 'http://fixture.invalid/chat/completions',
                         limit=limit, check=lambda: None, opener=transport)
    model = OpenAIModel('http://fixture.invalid', 'fixture', revision='fixture',
                        http=HTTP(allow_network=True, opener=cap), expected_response_model='fixture')
    h = Harness('Synthetic sources boundary', smoke_corpus(), config=Config(max_model_calls=64),
                answer_contract=INTEGER_ANSWER)
    try:
        result = observe(h, model, cap)
        assert result['status'] == 'local_continuation_cap' and result['attempts'] == limit
        assert h.terminal is None and h.model_calls == limit and not h.final_phase()
        assert h.feedback['code'] == 'sources_required'
        assert len(list(tmp_path.glob('http/*/request.body'))) == limit
        assert len(list(tmp_path.glob('http/*/response.body'))) == limit
        with pytest.raises(ValueError, match='cap'):
            model.send({'model': 'fixture'})
        assert budget.snapshot()['this_run'] == limit
    finally: h.close(); budget.close()
