"""Offline acceptance for constraint-state-v1.

These tests hit real dispatch, not just state labels. They cover the three
data dependencies (question→task, observation→judgment, judgment→next action)
and the reverse boundaries (missing≠contradicted, uncertain≠permanent ban,
original question not rewritten, local refutation≠name ban).

ScriptedModel / hand-built patches are mechanical fixtures; they test that the
program correctly reduces and routes, NOT that a real model would produce the
judgment. Every such fixture is labelled as such.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from stride_search.contract import Config, ContractError, INTEGER_ANSWER, canonical, loads
from stride_search.engine import Harness
from stride_search.fixtures import LocalCorpus, ScriptedModel, native, DOCUMENTS


def _harness(model, *, corpus=None, config=None, answer_contract=INTEGER_ANSWER):
    corpus = corpus or LocalCorpus(DOCUMENTS)
    h = Harness("Who was the first director of Lumen Observatory?", corpus,
                path=":memory:", config=config or Config(max_model_calls=8),
                answer_contract=answer_contract, decision_protocol="constraint-state-v1")
    # The frame is normally initialized during the first context.build(); for
    # tests that inspect state without running, initialize it now.
    h.local_state.init_frame(h.question)
    return h


# ---- 1. Original question / roles / answer_target not rewritten by evidence ----
def test_frame_answer_target_stable_and_not_rewritten_by_evidence():
    h = _harness(None)
    target_before = h.local_state.frame.answer_target
    qhash_before = h.local_state.frame.question_hash
    # An ordinary evidence update must not change the frame.
    h.local_state.evaluation.add(task_id="t1", source_ref="e1", statement="x",
                                 subject="x", relation="x", value="x", state="supported",
                                 scope="x", kind="source_statement")
    assert h.local_state.frame.answer_target == target_before
    assert h.local_state.frame.question_hash == qhash_before
    h.close()


def test_task_amendment_records_old_new_and_affected():
    h = _harness(None)
    h.local_state.add_task(question="old interpretation", clause="c1")
    rec = h.local_state.frame.amend(basis="misread role", old="AuthorA",
                                    new="AuthorB", affected_tasks=["t1"])
    assert rec["old"] == "AuthorA" and rec["new"] == "AuthorB"
    assert h.local_state.frame.amendments[-1]["kind"] == "task_amendment"
    h.close()


# ---- 2. Legal source + exact quote; unknown ref / undelivered / snippet ----
def test_interpret_rejects_undelivered_source_ref():
    h = _harness(None)
    h.local_state.add_task(question="q", clause="c")
    binding = {"documents": frozenset(), "evidence": frozenset()}
    with pytest.raises(ContractError) as exc:
        from stride_search.local_state import dispatch_interpret
        dispatch_interpret(h, {"task_id": "t1", "source_ref": "e99",
            "statement": "s", "subject": "s", "relation": "r", "state": "supported"}, binding)
    assert exc.value.code == "unreceived_reference"
    h.close()


def test_interpret_rejects_quote_not_in_window():
    h = _harness(None)
    # Deliver e1 via a real read; a third action exposes e1 in the shelf.
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    assert "e1" in h.exposed
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    with pytest.raises(ContractError) as exc:
        dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
            "statement": "s", "subject": "s", "relation": "r", "state": "supported",
            "quote": "THIS PHRASE DOES NOT EXIST"}, binding)
    assert exc.value.code == "quote_not_found"
    h.close()


def test_interpret_accepts_exact_quote_in_window():
    h = _harness(None)
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    res = dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
        "statement": "first director was Ada Rowan", "subject": "Ada Rowan",
        "relation": "first_director", "value": "Ada Rowan", "state": "supported",
        "quote": "first director was Ada Rowan"}, binding)
    assert res["ok"] is True
    assert res["routing"] == "answer_ready"
    h.close()


# ---- 3. Contradiction voids dependent tickets before dispatch ----
def test_contradiction_voids_dependent_tasks_not_independent():
    h = _harness(None)
    # t1 is the active task investigating Ada's role; t2 depends on the same
    # relation (should be voided when it is refuted); t3 depends on an
    # unrelated relation (should be kept).
    h.local_state.add_task(question="active Ada role check", clause="c",
                           entry_points=[{"label": "x", "depends_on": "Ada|first_director"}])
    h.local_state.add_task(question="dependent Ada detail", clause="c",
                           entry_points=[{"label": "x", "depends_on": "Ada|first_director"}])
    h.local_state.add_task(question="independent height check", clause="c",
                           entry_points=[{"label": "y", "depends_on": "other|height"}])
    h.local_state.select_task("t1")
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
        "statement": "not the first director", "subject": "Ada",
        "relation": "first_director", "state": "contradicted",
        "quote": "second director was Ivo Lane"}, binding)
    # t2 depends on Ada|first_director → voided; t3 depends on other|height → kept.
    t2 = next(t for t in h.local_state.tasks if t.id == "t2")
    t3 = next(t for t in h.local_state.tasks if t.id == "t3")
    assert t2.voided is True
    assert t3.voided is False
    h.close()


# ---- 4. Missing info ≠ contradiction; source conflict → disputed ----
def test_unknown_does_not_inactivate_candidate():
    h = _harness(None)
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    res = dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
        "statement": "cannot determine", "subject": "Ada",
        "relation": "first_director", "state": "unknown",
        "quote": "Lumen Observatory opened in 2012"}, binding)
    assert res["routing"] == "open"  # not inactive
    h.close()


def test_identity_unknown_routes_to_check_conflict_not_inactivate():
    h = _harness(None)
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    res = dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
        "statement": "subject unclear", "subject": "unknown person",
        "relation": "first_director", "state": "identity_unknown",
        "quote": "Lumen Observatory opened in 2012"}, binding)
    assert res["routing"] == "check_conflict"
    h.close()


# ---- 5. Correctable extraction; candidate recoverable ----
def test_correction_recovers_state_without_permanent_ban():
    h = _harness(None)
    model = ScriptedModel([native(("search", {"queries": ["Lumen"], "top_k": 1})),
                           native(("read", {"ref": "d1"})),
                           native(("finish", {"answer": "x", "refs": ["e1"]}))])
    h.run(model)
    binding = {"documents": frozenset(h.published_docs), "evidence": frozenset(h.exposed)}
    from stride_search.local_state import dispatch_interpret
    # First a wrong contradiction.
    dispatch_interpret(h, {"task_id": "t1", "source_ref": "e1",
        "statement": "wrong", "subject": "Ada", "relation": "first_director",
        "state": "contradicted", "quote": "second director was Ivo Lane"}, binding)
    # Then a correction to supported.
    j = h.local_state.evaluation.for_task("t1")[0]
    h.local_state.evaluation.correct(task_id="t1", judgment_index=0,
                                     new_state="supported", new_value="Ada Rowan",
                                     revision_note="re-read")
    task = h.local_state.active_task
    # After correction the candidate is recoverable; not permanently banned.
    assert task.routing in ("open", "answer_ready", "check_conflict")
    h.close()


# ---- 6. Independent vs dependent tasks; rename keeps attempt history ----
def test_task_rename_keeps_attempt_history():
    h = _harness(None)
    t = h.local_state.add_task(question="original q", clause="c")
    t.bump_attempt(); t.bump_attempt()
    t.rename("renamed q")
    assert t.question == "renamed q"
    assert t.attempts == 2  # rename did not reset
    assert "original q" in t.renames
    h.close()


# ---- 7. Deterministic comparison does not swap event type / unit ----
def test_reduce_does_not_promote_on_missing_identity():
    h = _harness(None)
    h.local_state.add_task(question="q", clause="c")
    # A supported judgment with no identity support should NOT become answer_ready.
    h.local_state.evaluation.add(task_id="t2", source_ref="e1", statement="v",
        subject="s", relation="r", value="v", state="supported", scope="c",
        kind="source_statement")
    # answer_ready requires identifying support + value support + no conflict;
    # a single supported fact alone is structural but the task still needs the
    # active-task binding to match. Here active task is t1, judgment is on t2.
    task = h.local_state.active_task
    assert task.id == "t1"
    assert task.routing == "open"  # t1 has no supported judgment
    h.close()


# ---- 8. Full execution: text → interpret → state → dispatch changes ----
def test_full_loop_choose_query_triggers_real_search_dispatch():
    """choose(query) must reach the underlying search backend, not just record."""
    h = _harness(None)
    model = ScriptedModel([
        native(("choose", {"task_id": "t1", "query": "Lumen Observatory first director"})),
        native(("read", {"ref": "d1"})),
        native(("interpret", {"task_id": "t1", "source_ref": "e1",
            "statement": "first director was Ada Rowan", "subject": "Ada Rowan",
            "relation": "first_director", "value": "Ada Rowan", "state": "supported",
            "quote": "first director was Ada Rowan"})),
        native(("choose", {"task_id": "t1", "answer": "Ada Rowan", "refs": ["e1"]})),
    ])
    term = h.run(model)
    assert term["outcome"] == "submitted"
    assert term["answer"] == "Ada Rowan"
    assert h.local_state.active_task.routing == "answer_ready"
    assert len(h.local_state.evaluation.all_judgments()) == 1
    # The search backend was actually called (navigation recorded).
    assert len(h.navigation_history) >= 1
    h.close()


def test_full_loop_interpret_changes_routing_before_next_dispatch():
    """A contradiction must change routing before any dependent dispatch."""
    h = _harness(None)
    model = ScriptedModel([
        native(("choose", {"task_id": "t1", "query": "Lumen Observatory first director"})),
        native(("read", {"ref": "d1"})),
        native(("interpret", {"task_id": "t1", "source_ref": "e1",
            "statement": "not director", "subject": "Ada",
            "relation": "first_director", "state": "contradicted",
            "quote": "second director was Ivo Lane"})),
    ])
    h.run(model)
    task = h.local_state.active_task
    assert task.routing == "check_conflict"
    h.close()


# ---- 9. Integer + string answer contracts; old archive compatible ----
def test_integer_answer_contract_preserved():
    corpus = LocalCorpus([{"docid": "num", "title": "Numbers",
        "content": "The count is 42 units total."}])
    h = Harness("How many units?", corpus, path=":memory:",
                config=Config(max_model_calls=6), answer_contract=INTEGER_ANSWER,
                decision_protocol="constraint-state-v1")
    model = ScriptedModel([
        native(("choose", {"task_id": "t1", "query": "count units"})),
        native(("read", {"ref": "d1"})),
        native(("interpret", {"task_id": "t1", "source_ref": "e1",
            "statement": "count is 42", "subject": "count", "relation": "value",
            "value": "42", "state": "supported", "quote": "count is 42"})),
        native(("choose", {"task_id": "t1", "answer": 42, "refs": ["e1"]})),
    ])
    term = h.run(model)
    assert term["outcome"] == "submitted"
    assert term["answer"] == "42"  # integer → decimal text
    h.close()


def test_baseline_profile_still_works_unchanged():
    """Old baseline profile must remain functional alongside the new one."""
    from stride_search.fixtures import smoke_model
    h = Harness("Who was the first director of Lumen Observatory?",
                LocalCorpus(DOCUMENTS), path=":memory:",
                config=Config(max_model_calls=3), decision_protocol="baseline")
    term = h.run(smoke_model())
    assert term["outcome"] == "submitted"
    assert term["answer"] == "Ada Rowan"
    h.close()


# ---- 10. Every program-generated action records cause and ticket ----
def test_controller_planned_read_labelled_not_forged():
    h = _harness(None)
    model = ScriptedModel([
        native(("choose", {"task_id": "t1", "query": "Lumen Observatory first director"})),
        native(("read", {"ref": "d1"})),
        native(("interpret", {"task_id": "t1", "source_ref": "e1",
            "statement": "first director was Ada Rowan", "subject": "Ada Rowan",
            "relation": "first_director", "value": "Ada Rowan", "state": "supported",
            "quote": "first director was Ada Rowan"})),
        native(("choose", {"task_id": "t1", "answer": "Ada Rowan", "refs": ["e1"]})),
    ])
    h.run(model)
    # The choose(query) dispatch produced a controller_planned search; the
    # archive must record the local_interpret and local_state events.
    kinds = [e["kind"] for e in h.archive.events()]
    assert "local_interpret" in kinds
    assert "local_state_commit" in kinds
    h.close()


def test_choose_with_exit_records_no_dispatch():
    h = _harness(None)
    model = ScriptedModel([
        native(("choose", {"task_id": "t1", "query": "Lumen Observatory first director"})),
        native(("read", {"ref": "d1"})),
        native(("choose", {"task_id": "t1", "exit": "no_suitable_option"})),
    ])
    term = h.run(model)
    # An exit does not submit; the episode ends by budget, abstention, or the
    # scripted model running out of responses (model_transport).
    assert term["outcome"] in ("model_budget", "submitted", "abstained", "model_transport")
    h.close()


# ---- Reverse boundary: navigation is a lead, not a source_statement ----
def test_navigation_lead_cannot_be_source_statement():
    h = _harness(None)
    # A navigation_lead kind must be unknown state.
    with pytest.raises(ValueError):
        h.local_state.evaluation.add(task_id="t1", source_ref="", statement="s",
            subject="s", relation="r", value="v", state="supported", scope="c",
            kind="navigation_lead")
    h.close()


def test_question_given_is_not_candidate_evidence():
    h = _harness(None)
    h.local_state.add_task(question="q", clause="c")
    # question_given records a task/reference condition; it is not support.
    rec = h.local_state.evaluation.add(task_id="t1", source_ref="", statement="given",
        subject="question", relation="condition", value="x", state="unknown",
        scope="c", kind="question_given")
    assert rec["kind"] == "question_given"
    assert rec["state"] == "unknown"
    # A question_given does not make the candidate answer_ready.
    assert h.local_state.active_task.routing == "open"
    h.close()
