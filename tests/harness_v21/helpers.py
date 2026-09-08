from copy import deepcopy
from esr_harness.engine import Harness
from esr_harness.protocol import Config
from esr_harness.views import MemoryRetriever

DOCS = [{"docid": "d1", "title": "Lake", "content": "Mira won the Lake Cup in 2010."},
        {"docid": "d2", "title": "Lake", "content": "Taylor won the Lake Cup in 2008."},
        {"docid": "d3", "title": "Other", "content": "A different cup was won by Robin in 2009."}]

class StubAudit:
    identity = {"fixture": "state-contract-audit"}
    def __init__(self, value="supported"):
        self.value, self.inputs = value, []
    def audit(self, question, state, views):
        self.inputs.append(deepcopy((question, state, views)))
        if isinstance(self.value, Exception):
            raise self.value
        by_id = {v["observation_id"]: v for v in views}
        def check(v):
            return {"status": v, "reason": "fixture", "need": "" if v == "supported" else "Find the missing relation"}
        rows = []
        for c in state["claims"]:
            v = self.value if c["observation_ids"] else "unknown"
            quotes = [] if v == "unknown" else [{"observation_id": o, "quote": by_id[o]["raw_parts"][0]} for o in c["observation_ids"]]
            rows.append({"claim_id": c["claim_id"], **check(v), "quotes": quotes})
        return {"target": check(self.value if state["answer"] else "unknown"), "coverage": check("supported"), "claims": rows}

def env(**kwargs):
    return Harness("Find the winner two years before Mira", MemoryRetriever(DOCS), StubAudit(), **kwargs)

def opened(h, docid="d1", query="Lake", expose=True, **kw):
    s=h.execute("search", {"query": query})
    assert s["ok"], s
    r=h.execute("open_page", {"docid": docid, **kw})
    assert r["ok"], r
    oid=r["observation"]["observation_id"]
    if expose:
        h.record_exposure([oid], "test-explicit-delivery")
    return oid

def update(h, oid="o1", answer="Taylor", **kw):
    args={"answer": answer, "claim_updates": [{"claim_id": "c0", "finding": "Source relation", "observation_ids": [oid]}]}
    args.update(kw)
    return h.execute("update_state", args)
