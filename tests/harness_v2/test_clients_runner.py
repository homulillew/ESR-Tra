from copy import deepcopy
import json
import sqlite3

import pytest

from esr_harness.v2.audit import ModelAuditor
from esr_harness.v2.cli import load_question, main
from esr_harness.v2.client import ChatClient, ChatConfig, UsageBudget
from esr_harness.v2.demo import smoke
from esr_harness.v2.engine import Harness
from esr_harness.v2.ledger import Ledger
from esr_harness.v2.protocol import Config, HarnessError, canonical
from esr_harness.v2.runner import POLICY_SYSTEM, messages_for, replay, run
from esr_harness.v2.views import MemoryRetriever
from .conftest import DOCUMENTS, StubAuditor, opened, report_for, update


class Counter:
    identity = {"fixture": "constant-token-counter"}
    def __call__(self, messages, thinking):
        return 10


def response(text="{}", completion=5):
    return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": completion}}


def client(transport, *, budget=100, ledger=None, counter=None, **config):
    ledger = ledger or Ledger()
    if not ledger.header:
        ledger.initialize({"fixture": True})
    return ChatClient(ChatConfig(base_url="http://localhost:1234/v1", model="fixture", max_context_tokens=100,
                                 max_output_tokens=20, **config), counter or Counter(), UsageBudget(budget), ledger, transport)


def test_chat_usage_is_combined_and_persisted():
    c = client(lambda *a, **k: response(completion=5))
    c.complete([{"role": "user", "content": "question"}], "policy")
    c.complete([{"role": "user", "content": "audit"}], "audit")
    restored = UsageBudget(100, c.ledger.events())
    assert restored.completion_tokens == 10 and restored.prompt_tokens == 20
    assert restored.unknown_usage_requests == 0


def test_budget_caps_the_request_and_stops():
    bodies = []
    def transport(url, body, **kw):
        bodies.append(body)
        return response(completion=body["max_tokens"])
    c = client(transport, budget=7)
    c.complete([{"role": "user", "content": "x"}])
    assert bodies[0]["max_tokens"] == 7
    with pytest.raises(HarnessError) as exc:
        c.complete([{"role": "user", "content": "x"}])
    assert exc.value.code == "generation_budget_exhausted"


def test_unknown_usage_is_explicit_not_estimated():
    c = client(lambda *a, **k: {"choices": [{"message": {"content": "{}"}}]})
    with pytest.raises(HarnessError):
        c.complete([{"role": "user", "content": "x"}])
    assert c.budget.unknown_usage_requests == 1
    assert c.ledger.events()[-1]["usage"] is None


def test_transport_retry_is_bounded_and_keeps_same_input():
    bodies = []
    def transport(url, body, **kw):
        bodies.append(deepcopy(body))
        if len(bodies) == 1:
            raise HarnessError("service_error", "HTTP 503")
        return response()
    c = client(transport)
    c.complete([{"role": "user", "content": "question and full evidence"}])
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    assert c.budget.unknown_usage_requests == 1


def test_http_400_is_not_retried_or_downgraded():
    calls = []
    def transport(*args, **kw):
        calls.append(1)
        raise HarnessError("service_error", "HTTP 400")
    c = client(transport)
    with pytest.raises(HarnessError):
        c.complete([{"role": "user", "content": "question"}])
    assert len(calls) == 1


def test_context_overflow_does_not_call_transport():
    calls = []
    c = client(lambda *a, **kw: calls.append(1), counter=lambda *a: 1000)
    with pytest.raises(HarnessError) as exc:
        c.complete([{"role": "user", "content": "required evidence"}])
    assert exc.value.code == "context_overflow" and not calls


def test_credentials_are_not_in_journal(monkeypatch):
    monkeypatch.setenv("ESR_API_KEY", "SECRET_CANARY_123")
    def transport(url, body, headers, **kw):
        assert headers["Authorization"] == "Bearer SECRET_CANARY_123"
        return response()
    c = client(transport)
    c.complete([{"role": "user", "content": "question"}])
    assert "SECRET_CANARY" not in canonical(c.ledger.events())


def test_audit_retry_retains_question_and_evidence(env):
    update(env, opened(env))
    good = report_for(env.state, list(env.observations.values()))
    class Fake:
        identity = {"fixture": "json-repair"}
        def __init__(self):
            self.inputs = []
        def complete(self, messages, purpose):
            self.inputs.append(deepcopy(messages))
            return "broken JSON" if len(self.inputs) == 1 else canonical(good)
    fake = Fake()
    report = ModelAuditor(fake).audit(env.question, env.state, list(env.observations.values()))
    assert report == good and len(fake.inputs) == 2
    for messages in fake.inputs:
        combined = canonical(messages)
        assert env.question in combined and "Taylor won the Lake Cup in 2008" in combined
    assert fake.inputs[1][:2] == fake.inputs[0]


def test_audit_never_receives_policy_history(env):
    update(env, opened(env))
    class Fake:
        identity = {"fixture": "fresh-context"}
        def complete(self, messages, purpose):
            assert len(messages) == 2
            payload = json.loads(messages[1]["content"])
            assert set(payload) == {"question", "target", "answer", "claims", "observations"}
            return canonical(report_for(env.state, list(env.observations.values())))
    ModelAuditor(Fake()).audit(env.question, env.state, list(env.observations.values()))


def test_pending_view_survives_recent_history_compaction(env):
    opened(env)
    class OnlyZeroRecent:
        def fits(self, messages):
            return not json.loads(messages[-1]["content"])["recent_actions"]
    messages = messages_for(env, OnlyZeroRecent())
    payload = json.loads(messages[-1]["content"])
    assert payload["recent_actions"] == []
    assert payload["pending_observations"][0]["text"] == env.observations["o1"]["text"]


def test_no_context_fit_fails_without_dropping_pending(env):
    opened(env)
    class NeverFits:
        def fits(self, messages):
            return False
    with pytest.raises(HarnessError, match="none were dropped"):
        messages_for(env, NeverFits())
    assert env.pending == {"o1"}


def test_invalid_model_outputs_cannot_loop_forever():
    class Invalid:
        def fits(self, messages): return True
        def complete(self, messages, purpose): return 'not JSON'
    h = Harness("question", MemoryRetriever(DOCUMENTS), config=Config(mode="baseline", max_actions=4))
    result = run(h, Invalid())
    assert result["attempts"] == 4 and result["terminal"]["outcome"] == "budget_exhausted"


def test_synthetic_full_repair_smoke_and_readonly_replay(tmp_path):
    path = tmp_path / "smoke.sqlite"
    result = smoke(path)
    assert result["attempts"] == 7 and result["terminal"]["answer"] == "Taylor"
    restored = replay(str(path))
    assert restored.terminal["answer"] == "Taylor"
    assert restored.ledger.readonly


def test_loader_never_returns_gold(tmp_path):
    path = tmp_path / "questions.jsonl"
    path.write_text(canonical({"query_id": "q1", "query": "What is asked?", "answer": "GOLD_CANARY_123",
                               "gold_docids": ["secret_id"]}) + "\n", encoding="utf-8")
    assert load_question(str(path), "q1") == "What is asked?"


def test_duplicate_qid_rejected_instead_of_overwritten(tmp_path):
    path = tmp_path / "questions.jsonl"
    row = canonical({"query_id": "q1", "query": "question"}) + "\n"
    path.write_text(row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        load_question(str(path), "q1")


def test_replay_cannot_create_a_missing_database(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(ValueError):
        replay(str(path))
    assert not path.exists()


def test_replay_never_alters_legacy_schema(tmp_path):
    path = tmp_path / "legacy.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE task_states (version INTEGER)")
    db.commit()
    original = path.read_bytes()
    with pytest.raises(ValueError):
        replay(str(path))
    assert path.read_bytes() == original


def test_export_cannot_overwrite_ledger(env):
    with pytest.raises(ValueError):
        env.ledger.export(env.ledger.path)


def test_cli_smoke_runs_without_gpu_or_model_dependencies(capsys):
    assert main(["smoke"]) == 0
    assert json.loads(capsys.readouterr().out)["terminal"]["answer"] == "Taylor"
