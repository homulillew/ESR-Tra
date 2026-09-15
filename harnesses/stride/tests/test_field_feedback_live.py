"""Local fixtures only. Scripted completions are never model-effect evidence."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import sys
import urllib.error

import pytest
from stride_search.contract import canonical
from stride_search.fixtures import native
from stride_search.providers import HTTP, OpenAIModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/field_feedback'))
from live_pilot import (Budget, CASE, GuardedCapture, attach_live, continue_slot,
                        load_prefix, next_payload, replay)


@pytest.fixture
def tape():
    return load_prefix(CASE)


def ledger(path, cap=1000):
    # This test-only ledger is isolated under pytest tmp_path. Production opens rw.
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE budget (cap INTEGER NOT NULL)')
    db.execute('INSERT INTO budget VALUES (?)', (cap,))
    db.execute('CREATE TABLE requests (id INTEGER PRIMARY KEY,run TEXT,role TEXT,status TEXT,http_status INTEGER,usage TEXT)')
    db.commit(); db.close()
    return Budget(path, 'local-fixture', limit=16)


class Backend:
    def __init__(self, captured):
        self.identity = deepcopy(captured.identity)
        self.capabilities = deepcopy(captured.capabilities)
        self.calls = []

    def compile_query(self, query):
        return {'compiler': 'fixture', 'terms': [query]}

    def search(self, query, top_k):
        self.calls.append((query, top_k))
        return []


class Response(io.BytesIO):
    status = 200


class Transport:
    def __init__(self, budget, responses, after=lambda: None):
        self.budget, self.responses, self.after = budget, list(responses), after
        self.sent = []

    def open(self, request, timeout):
        # Verify the persistent charge and raw request exist before fake transport.
        assert self.budget.snapshot()['this_run'] == len(self.sent) + 1
        assert self.budget.db.execute('SELECT status FROM requests ORDER BY id DESC LIMIT 1').fetchone()[0] == 'unknown'
        self.sent.append(request.data)
        value = self.responses.pop(0)
        self.after()
        if isinstance(value, Exception):
            raise value
        return Response(canonical(value).encode())


def response(tool, args, *, model='glm-5.2', reason='tool_calls'):
    value = native((tool, args)); value['model'] = model
    value['choices'][0]['finish_reason'] = reason
    return value


def execute(tmp_path, tape, responses, mode='field', after=None):
    h, recorded = replay(tape, tmp_path / 'episode.sqlite', mode)
    budget = ledger(tmp_path / 'budget.sqlite')
    backend = Backend(h.retriever)
    clock = [100.0]
    transport = Transport(budget, responses, after=(lambda: after(clock)) if after else lambda: None)
    capture = GuardedCapture(tmp_path, budget, 'fixture-secret', 'http://localhost/v1/chat/completions', opener=transport)
    ident = recorded.identity
    model = OpenAIModel('http://localhost/v1', ident['model'], revision=ident['revision_label'],
        http=HTTP(allow_network=True, opener=capture), temperature=ident['temperature'],
        expected_response_model=ident['expected_response_model'], output_parameter=ident['output_parameter'])
    original = canonical(next_payload(h, recorded))
    attach_live(h, model, backend, clock=lambda: clock[0])
    assert canonical(next_payload(h, model)) == original
    assert h.remaining() == {'model_calls': 60, 'action_slots': 196, 'backend_calls': 113, 'output_reservation': 47648}
    result = continue_slot(h, model, capture, clock=lambda: clock[0])
    return h, budget, backend, transport, capture, result


@pytest.mark.parametrize('mode', ['legacy', 'field'])
def test_real_adapter_switch_capture_and_literal_submission(tmp_path, tape, mode):
    literal = '  "synthetic literal"\n'
    h, budget, backend, transport, capture, result = execute(tmp_path, tape,
        [response('finish', {'answer': literal, 'refs': ['e1']})], mode)
    try:
        assert result['status'] == 'submitted' and result['attempts'] == 1 and not result['stop_queue']
        assert h.terminal['answer'] == literal and h.terminal['refs'] == ['e1']
        assert h.config.max_model_calls == 64 and h.config.max_seconds == 1800 and not backend.calls
        assert transport.sent[0] == (tmp_path / 'http/001/request.body').read_bytes()
        assert json.loads((tmp_path / 'http/001/response.body').read_bytes())['model'] == 'glm-5.2'
        assert budget.snapshot()['this_run'] == 1
        assert capture.rows[0]['returned_model'] == 'glm-5.2'
    finally:
        h.close(); budget.close()


def test_four_numeric_errors_external_cap_and_feedback(tmp_path, tape):
    h, budget, backend, transport, capture, result = execute(tmp_path, tape,
        [response('finish', {'answer': 47, 'refs': ['e1']}) for _ in range(4)])
    try:
        assert result['status'] == 'local_continuation_cap' and result['attempts'] == 4
        assert not result['stop_queue'] and h.terminal is None and h.model_calls == 8
        assert h.remaining()['model_calls'] == 56 and not h.final_phase()
        wire = json.loads(transport.sent[-1])
        feedback = json.loads(wire['messages'][-1]['content'].split('\n', 1)[1])['feedback']
        receipts = [json.loads(m['content']) for m in wire['messages'] if m['role'] == 'tool']
        assert receipts[-1]['message'] == feedback['message']
        assert '/answer' in feedback['message'] and '47' not in feedback['message']
        assert budget.snapshot()['this_run'] == 4
    finally:
        h.close(); budget.close()


def test_new_search_goes_to_replacement_backend(tmp_path, tape):
    h, budget, backend, transport, capture, result = execute(tmp_path, tape, [
        response('search', {'queries': ['NEW SYNTHETIC QUERY'], 'top_k': 1}),
        response('finish', {'abstain': True, 'reason': 'fixture'})])
    try:
        assert result['status'] == 'abstained' and result['attempts'] == 2
        assert backend.calls == [('NEW SYNTHETIC QUERY', 1)] and h.backend_calls == 8
    finally:
        h.close(); budget.close()


@pytest.mark.parametrize('bad,status', [
    (response('finish', {'answer': 'synthetic', 'refs': ['e1']}, model='other'), 'model_identity_changed'),
    (response('finish', {'answer': 'synthetic', 'refs': ['e1']}, reason='length'), 'incomplete_response'),
    (urllib.error.HTTPError('http://localhost', 429, 'fixture', {}, io.BytesIO(b'fixture error')), 'http_error'),
    (TimeoutError('fixture'), 'transport_error'),
])
def test_failure_charged_and_stops_queue(tmp_path, tape, bad, status):
    h, budget, backend, transport, capture, result = execute(tmp_path, tape, [bad])
    try:
        assert result['status'] == status and result['stop_queue'] and result['attempts'] == 1
        assert budget.snapshot()['this_run'] == 1 and h.action_slots == 4
        assert (tmp_path / 'http/001/metadata.json').is_file()
    finally:
        h.close(); budget.close()


def test_real_local_clock_stops_without_harness_terminal(tmp_path, tape):
    h, budget, backend, transport, capture, result = execute(tmp_path, tape,
        [response('finish', {'answer': 47, 'refs': ['e1']})], after=lambda c: c.__setitem__(0, c[0] + 301))
    try:
        assert result['status'] == 'local_time_cap' and result['attempts'] == 1
        assert h.terminal is None and not h.final_phase() and h.config.max_seconds == 1800
    finally:
        h.close(); budget.close()


def test_budget_never_creates_or_resets(tmp_path):
    path = tmp_path / 'missing.sqlite'
    with pytest.raises(sqlite3.OperationalError):
        Budget(path, 'fixture', limit=16)
    assert not path.exists()
    with pytest.raises(ValueError, match='insufficient'):
        ledger(tmp_path / 'too-small.sqlite', cap=15)


def test_pre_send_integrity_gate_prevents_transport_and_charge(tmp_path):
    budget = ledger(tmp_path / 'budget.sqlite')
    transport = Transport(budget, [])
    def fail():
        raise ValueError('fixture frozen-code mismatch')
    capture = GuardedCapture(tmp_path, budget, '', 'http://localhost/v1/chat/completions', opener=transport, check=fail)
    try:
        with pytest.raises(ValueError, match='frozen-code'):
            HTTP(allow_network=True, opener=capture).post('http://localhost/v1/chat/completions', {'model': 'fixture'})
        assert budget.snapshot()['this_run'] == 0 and transport.sent == []
    finally:
        budget.close()
