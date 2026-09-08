"""Deterministic synthetic protocol fixture, NOT a BC+ or model capability result."""
import json
from .engine import Harness
from .ledger import Ledger
from .protocol import canonical
from .runner import run
from .views import MemoryRetriever


class DemoAuditor:
    identity = {"fixture": "two-source-lake-auditor-2.1"}
    def audit(self, question, state, views):
        by_id = {v["observation_id"]: v for v in views}
        complete = any("Taylor won" in v["text"] for v in views)
        value = "supported" if state["answer"] == "Taylor" and complete else "unknown"
        if state["answer"] not in {None, "Taylor"} and complete:
            value = "contradicted"
        def check(s):
            return {"status": s, "reason": "Synthetic relation fixture", "need": "" if s == "supported" else "Bind the earlier winner using both years"}
        claims = []
        for c in state["claims"]:
            quotes = []
            if value != "unknown":
                for oid in c["observation_ids"]:
                    v = by_id[oid]
                    text = v.get("raw_parts", [v["text"].split("\n", 1)[-1]])[0]
                    quotes.append({"observation_id": oid, "quote": text})
            claims.append({"claim_id": c["claim_id"], **check(value), "quotes": quotes})
        return {"target": check("unknown" if state["answer"] is None else value),
                "coverage": check("supported"), "claims": claims}


class DemoPolicy:
    """Scripted actions provide expected transitions, not model reasoning."""
    def __init__(self):
        self.step = 0
    def fits(self, messages):
        return True
    def complete(self, messages, purpose="policy"):
        steps = [
            ("search", {"query": "Mira"}),
            ("open_page", {"docid": "lake-2010"}),
            ("update_state", {"claim_updates": [{"claim_id": "c0", "finding": "Mira won Lake Cup in 2010; earlier winner unknown.", "observation_ids": ["o1"]}],
                              "focus": {"claim_id": "c0", "need": "Who won the same Lake Cup in 2008?"}}),
            ("verify_answer", {}),
            ("search", {"query": "Mira"}),
            ("read_evidence", {"observation_id": "o1"}),
            ("search", {"query": "Lake Cup 2008"}),
            ("open_page", {"docid": "lake-2008"}),
            ("update_state", {"answer": "Taylor", "claim_updates": [{"claim_id": "c0", "finding": "Mira won Lake Cup in 2010; Taylor won the same cup in 2008. 2010-2=2008.", "observation_ids": ["o1", "o2"]}], "focus": None}),
            ("verify_answer", {}),
            ("submit_answer", {"decision": "answer"}),
        ]
        name, args = steps[self.step]
        self.step += 1
        return canonical({"action": name, "arguments": args})


def smoke(path=":memory:"):
    h = Harness("Who won the same event two years before Mira won the Lake Cup in 2010?",
                MemoryRetriever([{"docid": "lake-2010", "title": "Lake record", "content": "Mira won the Lake Cup in 2010."},
                                 {"docid": "lake-2008", "title": "Lake record", "content": "Taylor won the Lake Cup in 2008."}]),
                DemoAuditor(), ledger=Ledger(path), manifest={"synthetic_protocol_fixture": True})
    if h.attempts:
        raise ValueError("Smoke requires a fresh ledger")
    result = run(h, DemoPolicy())
    h.ledger.verify()
    assert result["terminal"]["answer"] == "Taylor"
    assert result["search_cache_hits"] == 1
    assert h.exposed == {"o1", "o2"}
    h.ledger.close()
    return result
