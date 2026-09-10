"""Offline counterexamples for historical and proposed multi-tool execution.

Uses synthetic data only. Does not call a provider or the BC+ retrieval service.
These assertions document defects, not acceptance tests for a fixed runtime.
Run from the repository: python scripts/reproduce_tool_contract_gaps.py
"""
from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from api.lanz_client import LanzClient
from esr_grpo.rollout import AgentRunner, OpenAIChatPolicy, PolicyTurn, ToolCall
from esr_harness.context import visible_ids, workcard
from esr_harness.demo import DemoAuditor
from esr_harness.engine import Harness
from esr_harness.protocol import HarnessError, parse_object
from esr_harness.views import MemoryRetriever


class FakeEnvironment:
    question = "Synthetic tool protocol fixture"
    is_submitted = False
    submitted_answer = None

    def render_context(self, **kwargs):
        return {}

    def execute_parallel(self, calls, **kwargs):
        return [{"ok": True} for _ in calls]

    def execute_tool(self, *args, **kwargs):
        return {"ok": True}

    def snapshot(self):
        return {"synthetic": True}


class FakePolicy:
    def __init__(self, turn):
        self.turn = turn

    def next_turn(self, *args):
        return self.turn


def declared_ids(messages):
    return {c["id"] for m in messages for c in m.get("tool_calls", [])}


def result_ids(messages):
    return {m["tool_call_id"] for m in messages if m["role"] == "tool"}


def reproduce():
    findings = {}
    # Extract just this static function; importing the archived script would
    # execute its historical environment/path setup.
    path = ROOT / "move/stage0_report_restored/source_code/run_stage0_lanz.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LanzPolicy")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_extract_action")
    fn.decorator_list = []
    namespace = {"parse_object": parse_object, "HarnessError": HarnessError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(path), "exec"), namespace)
    first = {"action": "search", "arguments": {"query": "alpha"}}
    second = {"action": "search", "arguments": {"query": "beta"}}
    combined = json.dumps(first) + "\n" + json.dumps(second)
    extracted = json.loads(namespace["_extract_action"](combined))
    assert extracted == first
    findings["historical_first_json"] = {"input_actions": 2, "returned_actions": 1, "returned": extracted}

    native = {"content": [{"type": "tool_use", "id": "c1", "name": "search", "input": {"query": "alpha"}}]}
    text = LanzClient._extract_text(native)
    assert text == ""
    findings["text_helper_omits_native_blocks"] = {"native_calls": 1, "extracted_text": text}

    calls = tuple(ToolCall("search", {"query": str(i)}, f"call{i}") for i in range(1, 8))
    runner = AgentRunner(FakeEnvironment(), FakePolicy(PolicyTurn("", calls)), max_turns=1, compact_message_chars=None)
    output = runner.run()
    missing = sorted(declared_ids(output["messages"]) - result_ids(output["messages"]))
    assert missing == ["call6", "call7"]
    findings["legacy_default_cap"] = {"declared_calls": 7, "results": 5, "missing_result_ids": missing}

    class ShortEnvironment(FakeEnvironment):
        def execute_parallel(self, calls, **kwargs):
            return [{"ok": True}]

    short = AgentRunner(ShortEnvironment(), FakePolicy(PolicyTurn("", calls[:2])), max_turns=1, compact_message_chars=None).run()
    missing = sorted(declared_ids(short["messages"]) - result_ids(short["messages"]))
    assert missing == ["call2"]
    findings["legacy_zip_short_results"] = {"injected_backend_contract_violation": True, "missing_result_ids": missing}

    messages = [{"role": "system", "content": "fixture"}, {"role": "user", "content": "fixture"},
                {"role": "assistant", "content": "", "tool_calls": [{"id": f"c{i}"} for i in range(5)]}]
    messages.extend({"role": "tool", "tool_call_id": f"c{i}", "content": "ok"} for i in range(5))
    runner.compact_message_chars = 1
    runner._maybe_compact(messages, 0)
    dangling = sorted(result_ids(messages) - declared_ids(messages))
    assert len(dangling) == 5
    findings["legacy_compaction_splits_group"] = {"dangling_result_ids": dangling}

    raw = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "valid", "function": {"name": "search", "arguments": '{"query":"alpha"}'}},
        {"id": "invalid", "function": {"name": "search", "arguments": '{broken'}},
    ]}}]}
    with patch("esr_grpo.rollout._post_chat_with_retry", return_value=raw):
        policy = OpenAIChatPolicy("http://offline.invalid", "synthetic", api_key_env="ESR_OFFLINE_UNUSED_KEY")
        turn = policy.next_turn([], {})
    mixed = AgentRunner(FakeEnvironment(), FakePolicy(turn), max_turns=1, compact_message_chars=None).run()
    assert len(turn.dropped_notes) == 1 and declared_ids(mixed["messages"]) == {"valid"}
    assert not any("nudge" in t for t in mixed["turns"])
    findings["legacy_mixed_valid_invalid"] = {"raw_calls": 2, "normalized_calls": 1, "dropped_notes": 1, "recovery_nudge": False}

    retriever = MemoryRetriever([
        {"docid": "alpha", "title": "Fixture alpha", "content": "Alpha is a synthetic observation."},
        {"docid": "beta", "title": "Fixture beta", "content": "Beta is a synthetic observation."},
    ])
    h = Harness("Compare the synthetic alpha and beta observations", retriever, DemoAuditor())
    ready = h.readiness()["verify_answer"]["ready"]
    offered = "verify_answer" in {t["name"] for t in h.available_tools()}
    assert ready and not offered
    findings["current_readiness_vs_advertised_tools"] = {"empty_state_verify_ready": ready, "verify_offered": offered}
    def execute(name, **arguments):
        result = h.execute(name, arguments)
        assert result["ok"], result
        return result
    execute("search", query="synthetic")
    execute("open_page", docid="alpha")
    execute("open_page", docid="beta")
    h.record_exposure(visible_ids(h), "synthetic-delivery")
    execute("update_state", claim_updates=[{"claim_id": "c0", "finding": "Both sources are synthetic observations.", "observation_ids": ["o1", "o2"]}])
    assert not h.pending
    execute("read_evidence", observation_id="o1")
    execute("read_evidence", observation_id="o2")
    delivered = [v["observation_id"] for v in workcard(h)["visible_evidence"]]
    assert delivered == ["o2"]
    findings["proposed_naive_loop_loses_reread_delivery"] = {"current_runner_accepts_batch": False, "requested_views": ["o1", "o2"], "next_workcard_views": delivered, "missing_view": "o1"}
    h.ledger.close()
    return {"source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "model_api_calls": 0, "external_retrieval_calls": 0, "synthetic_only": True,
            "counterexample_count": len(findings), "findings": findings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON file; existing files are never overwritten")
    args = parser.parse_args()
    rendered = json.dumps(reproduce(), ensure_ascii=True, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    print(rendered)
