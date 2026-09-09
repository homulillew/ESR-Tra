from copy import deepcopy
from types import SimpleNamespace
import json
import pytest

from esr_harness.protocol import Config, STATE_SCHEMA, validate, HarnessError
from esr_harness.engine import Harness
from esr_harness.views import MemoryRetriever
from esr_harness.runner import messages_for, run
from esr_harness.client import UsageBudget
from esr_harness.ledger import Ledger
from esr_harness.remote import AnthropicClient, GlobalBudget, RemoteConfig
from .helpers import env, opened, update, DOCS


def test_long_question_has_valid_initial_state_and_can_bind_answer():
    h = Harness("Q" * 16000, MemoryRetriever(DOCS), config=Config(audit_mode="off"))
    validate({k:v for k,v in h.state.items() if k != "research_version"}, STATE_SCHEMA)
    assert h.execute("update_state", {"answer": "candidate"})["ok"]
    assert len(h.state["claims"][0]["requirement"]) == 16000


def test_auxiliary_association_failure_preserves_semantics_without_false_provenance():
    h=env(); oid=opened(h)
    result=update(h, oid, attempt_id="a999", attempt_note="read this source")
    assert result["ok"] and result["warnings"][0]["path"] == "arguments.attempt_id"
    assert h.state["answer"] == "Taylor" and not h.pending
    assert "attempt_note" not in h.actions[-1]["delta"]
    assert h.actions[-1]["arguments"]["attempt_note"] == "read this source"


def test_semantic_error_retains_proposal_for_single_local_repair():
    h=env(); oid=opened(h)
    patch={"answer":"Taylor","claim_updates":[{"claim_id":"c0","finding":"relation","observation_ids":[oid]}],
           "focus":{"claim_id":"c99","need":"relation"}}
    before=deepcopy(h.state)
    assert not h.execute("update_state",patch)["ok"] and h.state == before
    assert h.context()["failed_proposal"]["arguments"] == patch
    patch["focus"]["claim_id"]="c0"
    assert h.execute("update_state",patch)["ok"] and h.state["answer"]=="Taylor"


def test_read_cannot_overflow_pending_but_cited_reread_is_visible():
    h=env(config=Config(max_pending_views=1)); o1=opened(h)
    assert h.execute("update_state",{"dismiss_observation_ids":[o1]})["ok"]
    o2=opened(h,docid="d2")
    assert h.execute("read_evidence",{"observation_id":o1})["error_code"]=="context_capacity"
    assert h.pending=={o2}
    assert update(h,o2)["ok"]
    assert h.execute("read_evidence",{"observation_id":o2})["ok"]
    assert h.context()["visible_evidence"][0]["text"]==h.observations[o2]["text"]


def test_submit_readiness_uses_execution_preconditions():
    h=env()
    assert h.readiness()["submit_answer.answer"]["blocked_reason"][0] == h.execute("submit_answer")["error_code"]
    assert h.readiness()["submit_answer.abstain"]["ready"]
    update(h,opened(h)); h.execute("verify_answer")
    assert h.readiness()["verify_answer"]["cached"]
    assert h.readiness()["submit_answer.answer"]["ready"]


def test_baseline_retains_full_observations_and_query_results():
    h=env(config=Config(mode="baseline",audit_mode="off")); o=opened(h)
    h.execute("search",{"query":"Other"})
    messages=messages_for(h,SimpleNamespace(fits=lambda _:True))
    rendered=json.dumps(messages)
    returned = [json.loads(m["content"]) for m in messages if m["role"] == "user"]
    assert any(r.get("observation", {}).get("text") == h.observations[o]["text"] for r in returned)
    assert any('"results"' in m["content"] and 'd1' in m["content"] for m in messages)
    assert not any('"claim_updates"' in m["content"] for m in messages)


class Transport:
    base_url="http://fixture"
    def __init__(self, responses): self.responses=iter(responses); self.requests=[]
    def request(self, body, **kw):
        self.requests.append(deepcopy(body))
        value=next(self.responses)
        if isinstance(value,Exception): raise value
        return value,{"http_status":200,"request-id":"fixture"}


def response(stop="end_turn",usage=True):
    return {"model":"fixture-model","stop_reason":stop,"content":[{"type":"text","text":'{"action":"finish","arguments":{"answer":"fixture"}}'}],
            "usage":{"input_tokens":12,"output_tokens":7} if usage else {}}


def client(tmp_path, responses):
    ledger=Ledger(); ledger.initialize({"fixture":True})
    global_budget=GlobalBudget(tmp_path/'budget.sqlite')
    c=AnthropicClient(Transport(responses),UsageBudget(100),ledger,global_budget,
                      config=RemoteConfig(max_output_tokens=32,transport_attempts=1))
    return c


def test_actual_system_mapping_and_usage_receipts(tmp_path):
    c=client(tmp_path,[response()]); messages=[{"role":"system","content":"SYSTEM"},{"role":"user","content":"QUESTION"}]
    c.complete(messages)
    request=c.transport.requests[0]
    assert request["system"]=="SYSTEM" and request["messages"]==[messages[1]]
    assert c.budget.charged_tokens==7 and c.budget.prompt_tokens==12
    assert c.global_budget.summary()["purposes"][0]["charged_output_tokens"]==7
    assert c.ledger.events()[0]["request"]==request
    assert c.ledger.events()[1]["response"]==response()


def test_truncated_reply_charged_but_never_executed(tmp_path):
    c=client(tmp_path,[response("max_tokens")])
    with pytest.raises(HarnessError,match="max_tokens") as exc:
        c.complete([{"role":"user","content":"fixture"}])
    assert exc.value.code=="output_truncated" and c.budget.charged_tokens==7


def test_unknown_usage_and_restart_keep_reservation(tmp_path):
    c=client(tmp_path,[response(usage=False)])
    with pytest.raises(HarnessError): c.complete([{"role":"user","content":"fixture"}])
    assert c.budget.charged_tokens==32 and c.budget.unknown_usage_requests==1
    restored=GlobalBudget(tmp_path/'budget.sqlite')
    assert restored.summary()["purposes"][0]["charged_output_tokens"]==32


def test_global_reservation_rejects_overrun(tmp_path):
    b=GlobalBudget(tmp_path/'small.sqlite',input_limit=20,output_limit=10)
    b.reserve("policy",12,7)
    with pytest.raises(HarnessError): b.reserve("audit",12,7)


def test_native_tools_use_contract_and_reject_multiple_calls(tmp_path):
    from esr_harness.protocol import canonical
    cfg=Config(mode="baseline",audit_mode="off")
    messages=[{"role":"system","content":"Call one tool.\nTools:\n"+canonical(cfg.tools)},
              {"role":"user","content":"fixture"}]
    r=response();r["stop_reason"]="tool_use"
    r["content"]=[{"type":"tool_use","id":"call1","name":"finish","input":{"answer":"fixture"}}]
    c=client(tmp_path,[r,{**r,"content":r["content"]*2}])
    assert json.loads(c.complete(messages))["arguments"]=={"answer":"fixture"}
    body=c.transport.requests[0]
    assert body["tools"][0]["input_schema"]==cfg.tool_schema("search")
    assert "Tools:" not in body["system"] and body["tool_choice"]["disable_parallel_tool_use"]
    with pytest.raises(HarnessError,match="exactly one"): c.complete(messages)


def test_context_check_is_finite(tmp_path):
    c=client(tmp_path,[])
    assert not c.fits([{"role":"user","content":"X"*70000}])


def test_cpu_index_search_document_consistency(tmp_path):
    import sqlite3
    from esr_harness.local_retrieval import SQLiteRetriever
    p=tmp_path/'index.sqlite';db=sqlite3.connect(p)
    db.executescript("CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE docs(docid TEXT,content TEXT,url TEXT);"
                     "CREATE VIRTUAL TABLE search USING fts5(content, content='docs', content_rowid='rowid', tokenize='porter unicode61');")
    db.execute("INSERT INTO metadata VALUES('identity',?)",(json.dumps({"complete":True,"corpus_hash":"synthetic"}),))
    db.execute("INSERT INTO docs VALUES('1','Orin Observatory opened in 2041.','fixture')")
    db.execute("INSERT INTO search(search) VALUES('rebuild')");db.commit();db.close()
    events=[];r=SQLiteRetriever(p,log=events.append)
    assert r.search('Orin " OR *',5)[0]['docid']=='1'
    assert r.get_document('1')['content']=='Orin Observatory opened in 2041.'
    assert [e['operation'] for e in events]==['search','get_document']
