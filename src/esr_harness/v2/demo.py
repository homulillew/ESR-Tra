"""A synthetic protocol smoke, NOT a language-model capability evaluation."""
from __future__ import annotations
import json
from .engine import Harness
from .ledger import Ledger
from .protocol import canonical
from .runner import run
from .views import MemoryRetriever


class DemoAuditor:
    identity = {"fixture": "lake-cup-auditor-v1"}
    def audit(self, question, state, views):
        value = "supported" if state["answer"] == "Taylor" else "contradicted"
        quote = "Taylor won the Lake Cup in 2008."
        return {"target": {"status": value, "reason": "Synthetic target-binding fixture"},
                "coverage": {"status": "supported", "reason": "Two-year relation is explicit"},
                "claims": [{"claim_id": "c1", "status": value,
                            "quotes": [{"observation_id": views[0]["observation_id"], "quote": quote}],
                            "reason": "The requested winner is Taylor, not the intermediate Alex"}]}


class DemoPolicy:
    def __init__(self):
        self.step = 0
    def fits(self, messages):
        return True
    def complete(self, messages, purpose="policy"):
        context = json.loads(messages[-1]["content"])
        steps = ["search", "open_page", "update_state", "verify_answer", "update_state", "verify_answer", "submit_answer"]
        name, args = steps[self.step], {}
        if name == "search":
            args = {"query": "Lake Cup"}
        elif name == "open_page":
            result = context["recent_actions"][-1]["result"]
            args = {"docid": result["results"][0]["docid"], "search_action_id": result["action_id"]}
        elif name == "update_state":
            oid = context["observation_directory"][0]["observation_id"]
            args = {"answer": "Alex" if self.step == 2 else "Taylor", "answer_kind": "answer",
                    "target": "Lake Cup winner two years before Alex",
                    "claims": [{"claim_id": "c1", "requirement": "The requested winner won two years before Alex",
                                "observation_ids": [oid]}]}
        self.step += 1
        return canonical({"action": name, "arguments": args})


def smoke(path=":memory:") -> dict:
    retriever = MemoryRetriever([{"docid": "lake", "title": "Lake Cup", "content":
                                 "Alex won the Lake Cup in 2010. Taylor won the Lake Cup in 2008."}])
    h = Harness("Who won the Lake Cup two years before Alex won in 2010?", retriever,
                DemoAuditor(), ledger=Ledger(path), manifest={"synthetic_protocol_fixture": True})
    if h.attempts:
        raise ValueError("Smoke requires a fresh ledger")
    result = run(h, DemoPolicy())
    h.ledger.verify()
    assert result["terminal"]["answer"] == "Taylor"
    assert any(a["result"].get("resolved_claim_ids") == ["c1"] for a in h.actions)
    h.ledger.close()
    return result
