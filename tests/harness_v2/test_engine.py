from copy import deepcopy
import json
import sqlite3

import pytest

from esr_harness.v2.engine import Harness
from esr_harness.v2.ledger import Ledger
from esr_harness.v2.protocol import Config, HarnessError
from esr_harness.v2.runner import replay
from esr_harness.v2.views import MemoryRetriever
from .conftest import DOCUMENTS, StubAuditor, opened, report_for, update


def test_supported_path(env):
    oid = opened(env)
    assert update(env, oid)["ok"]
    verified = env.execute("verify_answer")
    assert verified["audit"]["status"] == "supported"
    assert env.execute("submit_answer")["terminal"]["answer"] == "Taylor"
    assert env.attempts == 5


def test_read_before_registration(env):
    oid = opened(env)
    assert env.state["research_version"] == 0
    assert env.execute("read_evidence", {"observation_id": oid})["ok"]


def test_observation_is_exact_and_defensively_copied(env):
    oid = opened(env)
    first = deepcopy(env.observations[oid])
    result = env.execute("read_evidence", {"observation_id": oid})
    result["observation"]["text"] = "injected"
    env.retriever.documents["d1"]["content"] = "changed server text"
    assert env.execute("read_evidence", {"observation_id": oid})["observation"] == first
    update(env, oid)
    env.execute("verify_answer")
    assert env.auditor.inputs[-1][2][0]["text"] == first["text"]


def test_query_specific_views_not_first_search_reconstruction(tmp_path):
    class Chunks(MemoryRetriever):
        def get_doc_chunks(self, docid, query, topk=3):
            text = "First fact." if query == "first" else "Last fact."
            return {"chunks": [{"text": text}]}
    r = Chunks([{"docid": "d1", "content": "First fact. middle Last fact.", "title": "first last"}])
    h = Harness("question", r, StubAuditor())
    first = opened(h, "first")
    second = opened(h, "last")
    assert first != second
    update(h, second, dismiss_observation_ids=[first])
    h.execute("verify_answer")
    assert "Last fact." in h.auditor.inputs[-1][2][0]["text"]
    assert "First fact." not in h.auditor.inputs[-1][2][0]["text"]
    assert "First fact." in h.execute("read_evidence", {"observation_id": first})["observation"]["text"]


def test_noop_update_preserves_version_and_cache(env):
    oid = opened(env)
    update(env, oid)
    first = env.execute("verify_answer")
    version = env.state["research_version"]
    assert update(env, oid)["noop"]
    assert env.state["research_version"] == version
    second = env.execute("verify_answer")
    assert second["cached"] and first["audit"] == second["audit"]
    assert env.auditor.calls == 1


def test_duplicate_open_cannot_reset_stagnation(env):
    oid = opened(env)
    update(env, oid)
    for _ in range(4):
        assert opened(env) == oid
    assert len(env.observations) == 1
    assert env.stagnant_actions >= env.config.stagnant_after
    assert any("No new raw-text" in g for g in env.context()["guidance"])


def test_irrelevant_open_can_be_dismissed_without_finding(env):
    oid = opened(env)
    extra = opened(env, "Morgan", "d2")
    assert update(env, oid)["ok"]
    assert extra in env.pending
    assert env.execute("verify_answer")["error_code"] == "pending_observations"
    assert update(env, oid, dismiss_observation_ids=[extra])["ok"]
    assert not env.pending and env.execute("verify_answer")["ok"]


def test_new_open_cannot_silently_bypass_final_processing(env):
    oid = opened(env)
    update(env, oid)
    env.execute("verify_answer")
    opened(env, "Morgan", "d2")
    assert env.execute("submit_answer")["error_code"] == "pending_observations"


@pytest.mark.parametrize("name,args", [
    ("open_page", {"docid": "d1", "search_action_id": "a99"}),
    ("read_evidence", {"observation_id": "cross_episode"}),
    ("read_evidence", {"observation_id": "o1", "offset": 10}),
    ("search", {"query": "x", "top_k": True}),
    ("search", {"query": ""}),
    ("finish", {"answer": "bypass"}),
    ("_submit", {}), ("execute", {}), ("close", {}),
])
def test_invalid_actions_are_logged_without_state_mutation(env, name, args):
    before = deepcopy(env.state)
    result = env.execute(name, args)
    assert not result["ok"] and env.state == before
    assert env.attempts == 1 and len(env.ledger.events()) == 1


def test_wrong_parent_search_rejected(env):
    found = env.execute("search", {"query": "Lake"})
    assert not env.execute("open_page", {"docid": "d2", "search_action_id": found["action_id"]})["ok"]


@pytest.mark.parametrize("value", ["unknown", "contradicted"])
def test_hard_mode_preserves_rejection(env, value):
    env.auditor.value = value
    oid = opened(env)
    update(env, oid)
    env.execute("verify_answer")
    assert env.execute("submit_answer")["error_code"] == "not_supported"
    assert env.terminal is None


@pytest.mark.parametrize("value", ["unknown", "contradicted"])
def test_soft_mode_finishes_without_forging_supported(value):
    h = Harness("question", MemoryRetriever(DOCUMENTS), StubAuditor(value), config=Config(audit_mode="soft"))
    update(h, opened(h))
    assert h.execute("submit_answer")["error_code"] == "audit_required"
    h.execute("verify_answer")
    assert h.execute("submit_answer")["terminal"]["evidence_status"] == value


def test_off_mode_has_no_dead_verify_tool():
    h = Harness("question", MemoryRetriever(DOCUMENTS), config=Config(audit_mode="off"))
    assert "verify_answer" not in [t["name"] for t in h.config.tools]
    update(h, opened(h))
    assert h.execute("submit_answer")["terminal"]["evidence_status"] == "unverified"


def test_baseline_read_is_not_a_dead_tool():
    h = Harness("question", MemoryRetriever(DOCUMENTS), config=Config(mode="baseline"))
    oid = opened(h)
    assert h.execute("read_evidence", {"observation_id": oid})["ok"]
    assert h.execute("finish", {"answer": "Taylor"})["terminal"]["answer"] == "Taylor"


def test_abstention_is_not_an_answer_or_supported(env):
    assert update(env, answer="not found", answer_kind="abstain", claims=[])["error_code"] == "protocol_error"
    assert update(env, answer="", answer_kind="abstain", claims=[])["ok"]
    terminal = env.execute("submit_answer")["terminal"]
    assert terminal == {"outcome": "abstained", "answer": "", "evidence_status": "unverified"}


def test_changed_answer_invalidates_audit(env):
    update(env, opened(env))
    env.execute("verify_answer")
    update(env, answer="Alex")
    assert env.current_audit is None
    assert env.context()["audit_stale"]
    assert env.execute("submit_answer")["error_code"] == "audit_required"


def test_research_resume_preserves_views_pending_and_cache(env):
    oid = opened(env)
    update(env, oid)
    env.execute("verify_answer")
    restored = Harness(env.question, env.retriever, StubAuditor(), config=env.config, ledger=Ledger(env.ledger.path))
    assert restored.state == env.state and restored.observations == env.observations
    assert restored.execute("verify_answer")["cached"]
    assert restored.auditor.calls == 0


def test_replay_is_readonly(env):
    update(env, opened(env))
    env.execute("verify_answer")
    before = len(env.ledger.events())
    restored = replay(env.ledger.path)
    assert restored.current_audit == env.current_audit
    with pytest.raises(RuntimeError):
        restored.execute("submit_answer")
    assert len(env.ledger.events()) == before


@pytest.mark.parametrize("exc", [HarnessError("service_error", "HTTP 503"),
                                 HarnessError("context_overflow", "too long"),
                                 HarnessError("audit_protocol_error", "malformed")])
def test_audit_errors_do_not_create_gaps_or_mutate_state(env, exc):
    update(env, opened(env))
    before = deepcopy(env.state)
    env.auditor.value = exc
    result = env.execute("verify_answer")
    assert result["error_code"] == exc.code
    assert env.state == before and env.last_audit is None and not env.audit_cache
    env.auditor.value = "supported"
    assert env.execute("verify_answer")["ok"]


def test_claim_deletion_requires_reason_and_never_resolves_gap(env):
    update(env, opened(env))
    env.auditor.value = "unknown"
    env.execute("verify_answer")
    assert not update(env, claims=[])["ok"]
    assert update(env, claims=[], revision_reason="Question decomposition was incorrect")["ok"]
    assert env.actions[-1]["delta"]["removed_claim_ids"] == ["c1"]
    assert "resolved_claim_ids" not in env.actions[-1]["result"]
    assert not env.execute("verify_answer")["ok"]


def test_rewording_requirement_does_not_count_as_gap_resolution(env):
    update(env, opened(env))
    env.auditor.value = "unknown"
    env.execute("verify_answer")
    claims = [{"claim_id": "c1", "requirement": "A different claim", "observation_ids": ["o1"]}]
    assert update(env, claims=claims, revision_reason="Replace an incorrect requirement")["ok"]
    env.auditor.value = "supported"
    assert env.execute("verify_answer")["resolved_claim_ids"] == []


def test_real_claim_repair_is_recorded(env):
    update(env, opened(env), answer="Alex")
    env.auditor.value = "unknown"
    env.execute("verify_answer")
    update(env, answer="Taylor")
    env.auditor.value = "supported"
    assert env.execute("verify_answer")["resolved_claim_ids"] == ["c1"]


def test_unknown_reworded_reason_is_still_unresolved(env):
    update(env, opened(env))
    env.auditor.value = "unknown"
    env.execute("verify_answer")
    update(env, answer="Alex")
    report = env.execute("verify_answer")
    assert report["resolved_claim_ids"] == []
    assert report["audit"]["unresolved_ids"] == ["@target", "@coverage", "c1"]


def test_failed_journal_commit_does_not_apply_transition(env, monkeypatch):
    before = deepcopy(env.state)
    def fail(_):
        raise sqlite3.OperationalError("disk failure")
    monkeypatch.setattr(env.ledger, "append", fail)
    with pytest.raises(sqlite3.OperationalError):
        env.execute("search", {"query": "Lake"})
    assert env.state == before and not env.searches and not env.actions


def test_unknown_action_budget_is_finite():
    h = Harness("question", MemoryRetriever(DOCUMENTS), config=Config(mode="baseline", max_actions=3))
    for _ in range(3):
        assert not h.execute("nonsense")["ok"]
    assert h.execute("search", {"query": "Lake"})["error_code"] == "budget_exhausted"
    assert h.terminal["outcome"] == "budget_exhausted"


def test_last_action_can_submit(env):
    h = Harness("question", env.retriever, env.auditor, config=Config(max_actions=5))
    update(h, opened(h))
    h.execute("verify_answer")
    assert h.execute("submit_answer")["ok"]
    before = len(h.ledger.events())
    assert h.execute("search", {"query": "Lake"})["error_code"] == "episode_finished"
    assert len(h.ledger.events()) == before


def test_header_model_config_change_cannot_resume(env):
    with pytest.raises(ValueError, match="header mismatch"):
        Harness("another question", env.retriever, env.auditor, ledger=Ledger(env.ledger.path))


def test_journal_sql_immutability(env):
    opened(env)
    with pytest.raises(sqlite3.IntegrityError):
        env.ledger.db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(sqlite3.IntegrityError):
        env.ledger.db.execute("DELETE FROM header")


def test_hash_chain_detects_external_tampering(env):
    opened(env)
    env.ledger.db.execute("DROP TRIGGER immutable_event_update")
    env.ledger.db.execute("UPDATE events SET payload='{}' WHERE seq=1")
    env.ledger.db.commit()
    with pytest.raises(ValueError, match="Corrupt ledger"):
        env.ledger.verify()


def test_competing_writer_detected(env):
    other = Ledger(env.ledger.path)
    other.append({"type": "test"})
    with pytest.raises(RuntimeError, match="Concurrent writer"):
        env.execute("search", {"query": "Lake"})
    assert not env.searches
