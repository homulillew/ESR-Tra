from copy import deepcopy
import json
import pytest
from esr_harness.context import visible_ids
from esr_harness.engine import Harness
from esr_harness.ledger import Ledger
from esr_harness.protocol import Config, HarnessError, canonical
from esr_harness.runner import messages_for, replay, run
from esr_harness.views import MemoryRetriever, make_view, document
from .helpers import env, opened, update, DOCS


def test_exact_cache_key_includes_k_and_never_resets_with_focus():
    h=env(); calls=[]; original=h.retriever.search
    h.retriever.search=lambda q,k: (calls.append((q,k)) or original(q,k))
    a=h.execute("search",{"query":"Lake"})
    b=h.execute("search",{"query":"Lake","focus":{"claim_id":"c0","need":"Changed wording"}})
    assert b["cached"] and b["cache_source"]==a["action_id"] and len(calls)==1
    h.execute("update_state",{"answer":"Different candidate"})
    assert h.execute("search",{"query":"Lake"})["cached"]
    assert not h.execute("search",{"query":"Lake","top_k":3})["cached"] and len(calls)==2

@pytest.mark.parametrize("query",["Lake 2008","Lake 2010","before Lake","after Lake"])
def test_small_query_changes_are_not_blocked(query):
    h=env(); h.execute("search",{"query":"Lake"}); assert h.execute("search",{"query":query})["ok"]


def test_unpinned_or_nondeterministic_retrieval_does_not_cache():
    h=env(); h.retriever.deterministic=False
    for _ in range(2): assert not h.execute("search",{"query":"Lake"})["cached"]


def test_declared_index_cannot_change_mid_episode():
    h=env(); h.retriever.identity["index_revision"]="new-index"
    assert h.execute("search",{"query":"Lake"})["error_code"]=="service_error"


def test_search_focus_survives_only_external_failure():
    h=env(); old=h.state["focus"]
    r=h.execute("search",{"query":"Lake","focus":{"claim_id":"c0","need":"illegal anchor route"},"anchor_refs":["o999"]})
    assert not r["ok"] and h.state["focus"]==old
    def fail(*a): raise HarnessError("service_error","timeout")
    h.retriever.search=fail
    r=h.execute("search",{"query":"Lake","focus":{"claim_id":"c0","need":"New legal route"}})
    assert not r["ok"] and r["focus_edit_applied"] and h.state["focus"]["need"]=="New legal route"
    assert not h.audit_cache and not h.searches


def test_open_parent_is_inferred_but_checked():
    h=env(); a=h.execute("search",{"query":"Lake"})
    b=h.execute("open_page",{"docid":"d1"}); assert b["retrieval_parent"]==a["action_id"]
    assert not h.execute("open_page",{"docid":"d3","search_action_id":a["action_id"]})["ok"]
    h.execute("search",{"query":"Lake","focus":{"claim_id":"c0","need":"New purpose"}})
    c=h.execute("open_page",{"docid":"d1"})
    assert c["duplicate_view"] and c["purpose"]["need"]=="New purpose"
    assert c["observation"]["created_by_action_id"]==b["action_id"]


def test_read_cited_view_pinned_even_with_zero_history():
    h=env(config=Config(recent_actions=0)); o=opened(h); update(h,o)
    h.execute("read_evidence",{"observation_id":o})
    assert not h.pending and visible_ids(h)==[o]
    class Fits:
        def fits(self,messages): return True
    p=json.loads(messages_for(h,Fits())[-1]["content"])
    assert p["visible_evidence"][0]["text"]==h.observations[o]["text"] and not p["recent_actions"]
    assert "raw_parts" not in canonical(p)
    assert canonical(p).count("Mira won the Lake Cup in 2010.")==1


def test_directory_pagination_and_read_are_reachable():
    h=env(config=Config(directory_page_size=1)); opened(h); opened(h,"d2")
    r=h.execute("read_evidence",{"directory_cursor":"start"})
    assert r["directory"][0]["observation_id"]=="o1"
    c=r["next_cursor"]; assert c
    r=h.execute("read_evidence",{"directory_cursor":c}); assert r["directory"][0]["observation_id"]=="o2"
    assert not h.execute("read_evidence",{"directory_cursor":"forged"})["ok"]
    assert not h.execute("read_evidence",{"directory_cursor":"start","observation_id":"o1"})["ok"]


def test_capacity_admission_shrinks_once_before_return():
    h=Harness("question",MemoryRetriever([{"docid":"long","content":"abcdef "*2000}]), config=Config(mode="baseline",view_chars=4000))
    h.admission=lambda p: sum(len(v["text"]) for v in p.context()["visible_evidence"]) < 800
    h.execute("search",{"query":"abcdef"})
    r=h.execute("open_page",{"docid":"long"}); assert r["ok"]
    v=r["observation"]; assert len(v["text"]) < 800 and not v["fully_visible"]
    assert h.execute("read_evidence",{"observation_id":v["observation_id"]})["observation"]==v


def test_rejected_large_state_edit_does_not_apply():
    h=env(); o=opened(h); before=deepcopy(h.state)
    h.admission=lambda p: len(canonical(p.state))<500
    r=update(h,o,claim_updates=[{"claim_id":"c0","finding":"X"*1200,"observation_ids":[o]}])
    assert r["error_code"]=="context_capacity" and h.state==before and o in h.pending


def test_pending_buffer_returns_repairable_error():
    h=env(config=Config(max_pending_views=1)); o=opened(h)
    assert h.execute("open_page",{"docid":"d2"})["error_code"]=="context_capacity"
    assert update(h,o)["ok"]
    assert h.execute("open_page",{"docid":"d2"})["ok"]


def test_rank_before_document_position():
    class Chunks(MemoryRetriever):
        def get_doc_chunks(self,docid,query,topk):
            return {"chunks":[{"text":"TAIL RELEVANT"},{"text":"EARLY"}]}
    doc=document({"docid":"d","content":"EARLY filler TAIL RELEVANT"},"d")
    v=make_view(doc,Chunks([]),"relevant",limit=13,top_k=2)
    assert "TAIL RELEVANT" in v["text"] and "EARLY" not in v["text"]


def test_ambiguous_chunk_requires_validated_offset_or_explicit_fallback():
    class Chunks(MemoryRetriever):
        def get_doc_chunks(self,*a,**k): return {"chunks":[{"text":"repeat"}]}
    doc=document({"docid":"d","content":"repeat filler repeat"},"d")
    assert make_view(doc,Chunks([]),"repeat",limit=100,top_k=2)["fallback"]=="ambiguous_chunk_offset"


def test_attempt_note_is_linked_and_does_not_invalidate_audit():
    h=env(); update(h,opened(h)); h.execute("verify_answer"); fp=h.fingerprint()
    r=h.execute("update_state",{"attempt_note":"This viewed passage establishes the year only.","attempt_id":"a1"})
    assert r["ok"] and h.fingerprint()==fp
    assert h.context()["focus_attempts"][-1]["actor_report_not_verified"]
    result = h.execute("update_state",{"attempt_note":"x","attempt_id":"a999"})
    assert result["ok"] and result["warnings"][0]["code"] == "unlinked_note"
    assert "attempt_note" not in h.actions[-1]["delta"]
    assert h.fingerprint() == fp


def test_resume_replays_exposures_cache_and_ids(tmp_path):
    h=env(ledger=Ledger(tmp_path/"trace.db")); o=opened(h); update(h,o); h.execute("verify_answer")
    r=replay(str(tmp_path/"trace.db")); assert r.state==h.state and r.exposed=={o}
    assert r.current_audit==h.current_audit and r.search_cache==h.search_cache
    with pytest.raises(RuntimeError): r.execute("search",{"query":"Lake"})
    r.ledger.close(); h.ledger.close()


def test_last_action_can_submit_and_budget_retains_draft():
    h=env(config=Config(audit_mode="off",max_actions=4)); update(h,opened(h))
    assert h.execute("submit_answer")["ok"]
    h=env(config=Config(max_actions=3)); update(h,opened(h)); h.end("budget_exhausted")
    assert h.terminal["answer"]=="" and h.terminal["final_draft"]=="Taylor"


def test_token_admission_also_preserves_relevance_order():
    from esr_harness.views import shrink_view
    class Chunks(MemoryRetriever):
        def get_doc_chunks(self,*a,**k): return {"chunks":[{"text":"TAIL RELEVANT"},{"text":"EARLY"}]}
    v=make_view(document({"docid":"d","content":"EARLY filler TAIL RELEVANT"},"d"),Chunks([]),"q",limit=100,top_k=2)
    assert "EARLY" in v["text"]
    smaller=shrink_view(v,13)
    assert "TAIL RELEVANT" in smaller["text"] and "EARLY" not in smaller["text"]


def test_latest_error_reports_actual_protocol_problem():
    h=env(); h.record_protocol_error("Expected one JSON object, not a list")
    assert "not a list" in h.context()["latest_tool_result"]["error"]
