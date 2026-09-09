"""Rendered messages, not model quality: profiles must match available capabilities."""
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from esr_harness.audit import ModelAuditor
from esr_harness.engine import Harness
from esr_harness.prompts import AUDIT_PROMPT_VERSION, AUDIT_SYSTEM, POLICY_PROMPT_VERSION, policy_system
from esr_harness.protocol import Config, canonical, digest
from esr_harness.runner import messages_for, run
from esr_harness.views import MemoryRetriever
from .helpers import DOCS, StubAudit, opened, update


PROFILES = [("baseline", "off"), ("esr", "off"), ("esr", "hard"), ("esr", "soft")]


def environment(mode, audit_mode, **kwargs):
    config = Config(mode=mode, audit_mode=audit_mode, **kwargs)
    auditor = StubAudit() if mode == "esr" and audit_mode != "off" else None
    return Harness("Find the winner two years before Mira", MemoryRetriever(DOCS), auditor, config=config)


@pytest.mark.parametrize("mode,audit_mode", PROFILES)
def test_rendered_system_has_only_available_action_instructions(mode, audit_mode):
    h = environment(mode, audit_mode)
    messages = messages_for(h, SimpleNamespace(fits=lambda messages: True))
    instructions, serialized = messages[0]["content"].split("\nTools:\n")
    tools = json.loads(serialized)
    assert tools == h.available_tools()
    names = {t["name"] for t in tools}
    assert "verify_answer" not in names  # empty bootstrap has no material audit packet
    for unavailable in {"update_state", "verify_answer", "submit_answer", "finish"} - {t["name"] for t in h.config.tools}:
        assert unavailable not in instructions
    if mode == "baseline":
        assert "focus" not in instructions and "findings" not in instructions
        search = next(t for t in tools if t["name"] == "search")
        assert set(search["parameters"]["properties"]) == {"query", "top_k"}
    if mode == "esr" and audit_mode == "off":
        assert "current audit" not in instructions


def test_hard_and_soft_have_distinct_stopping_contracts():
    hard = policy_system(Config(audit_mode="hard"))
    soft = policy_system(Config(audit_mode="soft"))
    assert "only when its current audit is\nsupported" in hard
    assert "even if unsupported" in soft
    assert "even if unsupported" not in hard


def test_baseline_pending_does_not_request_nonexistent_state_actions():
    h = environment("baseline", "off")
    opened(h, expose=False)
    assert h.pending
    card = json.loads(messages_for(h, SimpleNamespace(fits=lambda messages: True))[1]["content"])
    assert set(card) == {"question"}
    assert "update_state" not in messages_for(h, SimpleNamespace(fits=lambda messages: True))[0]["content"]


@pytest.mark.parametrize("field,value", [
    ("focus", {"claim_id": "c0", "need": "relation"}),
    ("anchor_refs", ["question"]),
])
def test_baseline_runtime_matches_advertised_search_parameters(field, value):
    h = environment("baseline", "off")
    result = h.execute("search", {"query": "Lake", field: value})
    assert not result["ok"] and result["error_code"] == "protocol_error"
    assert not h.searches


def test_snapshot_covers_actual_system_message_and_audit_text():
    snapshot = json.loads((Path(__file__).parent / "fixtures" / "prompt_profiles.json").read_text())
    for mode, audit_mode in PROFILES:
        h = environment(mode, audit_mode)
        actual = messages_for(h, SimpleNamespace(fits=lambda messages: True))[0]["content"]
        assert snapshot[f"{mode}/{audit_mode}"] == sha256(actual.encode()).hexdigest()
    assert snapshot["audit"] == sha256(AUDIT_SYSTEM.encode()).hexdigest()
    assert snapshot["policy_version"] == POLICY_PROMPT_VERSION
    assert snapshot["audit_version"] == AUDIT_PROMPT_VERSION


def test_prompt_selection_does_not_change_evidence_or_state():
    h = environment("esr", "off")
    oid = opened(h)
    update(h, oid)
    assert h.execute("read_evidence", {"observation_id": oid})["ok"]
    before = canonical(h.state)
    messages = messages_for(h, SimpleNamespace(fits=lambda messages: True))
    card = json.loads(messages[1]["content"])
    assert canonical(h.state) == before
    assert any(v["observation_id"] == oid and v["text"] == h.observations[oid]["text"]
               for v in card["visible_evidence"])


def test_policy_receipt_records_prompt_version_and_actual_hash():
    h = environment("baseline", "off", max_actions=1)
    client = SimpleNamespace(fits=lambda messages: True,
                             complete=lambda *args, **kwargs: '{"action":"finish","arguments":{"answer":"Taylor"}}')
    run(h, client)
    decision = next(e for e in h.ledger.events() if e["type"] == "decision")
    assert decision["policy_prompt_version"] == POLICY_PROMPT_VERSION
    assert decision["policy_system_hash"] == digest(decision["messages"][0]["content"])


def test_audit_identity_hashes_exact_prompt_and_preserves_inference_boundary():
    auditor = ModelAuditor(SimpleNamespace(identity={"fixture": True}))
    assert auditor.identity["prompt"] == AUDIT_PROMPT_VERSION
    assert auditor.identity["system_hash"] == digest(AUDIT_SYSTEM)
    assert "Logical and arithmetic inference from explicit premises is allowed" in AUDIT_SYSTEM
    assert "Do not supply missing facts from\nmemory or answer labels" in AUDIT_SYSTEM
    assert "tournament" not in AUDIT_SYSTEM and "q324" not in AUDIT_SYSTEM
