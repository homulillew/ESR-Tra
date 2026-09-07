from copy import deepcopy
import pytest

from esr_harness.engine import Harness
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config, HarnessError
from esr_harness.views import MemoryRetriever

DOCUMENTS = [
    {"docid": "d1", "title": "Lake Cup records", "content": "Alex won the Lake Cup in 2010. Taylor won the Lake Cup in 2008."},
    {"docid": "d2", "title": "Unrelated", "content": "Morgan won a different tournament in 2009."},
]


def report_for(state, views, value="supported", reason="fixture judgement"):
    by_id = {v["observation_id"]: v for v in views}
    claims = []
    for c in state["claims"]:
        quotes = []
        if value != "unknown" and c["observation_ids"]:
            oid = c["observation_ids"][0]
            quotes = [{"observation_id": oid, "quote": by_id[oid]["raw_parts"][0]}]
        claims.append({"claim_id": c["claim_id"], "status": value, "quotes": quotes, "reason": reason})
    return {"target": {"status": value, "reason": reason},
            "coverage": {"status": value, "reason": reason}, "claims": claims}


class StubAuditor:
    identity = {"fixture": "stub-auditor-v1"}
    def __init__(self, value="supported"):
        self.value, self.calls, self.inputs = value, 0, []
    def audit(self, question, state, views):
        self.calls += 1
        self.inputs.append(deepcopy((question, state, views)))
        if isinstance(self.value, Exception):
            raise self.value
        return report_for(state, views, self.value)


@pytest.fixture
def env(tmp_path):
    h = Harness("Who won the Lake Cup two years before Alex?", MemoryRetriever(DOCUMENTS), StubAuditor(),
                ledger=Ledger(tmp_path / "episode.sqlite"))
    yield h
    h.ledger.close()


def opened(h, query="Lake", docid="d1", **kw):
    found = h.execute("search", {"query": query})
    assert found["ok"], found
    result = h.execute("open_page", {"docid": docid, "search_action_id": found["action_id"], **kw})
    assert result["ok"], result
    return result["observation"]["observation_id"]


def update(h, oid="o1", answer="Taylor", **kw):
    args = {"answer": answer, "answer_kind": "answer", "target": "Winner two years before Alex",
            "claims": [{"claim_id": "c1", "requirement": "The requested winner is two years before Alex", "observation_ids": [oid]}]}
    args.update(kw)
    return h.execute("update_state", args)
