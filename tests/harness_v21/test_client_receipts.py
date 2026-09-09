import json
import pytest
from esr_harness.audit import ModelAuditor, validate_report
from esr_harness.client import ChatClient, ChatConfig, UsageBudget
from esr_harness.demo import smoke
from esr_harness.ledger import Ledger
from esr_harness.protocol import HarnessError
from esr_harness.runner import replay, run
from .helpers import env, opened, update


def client(transport,budget=100):
    l=Ledger(); l.initialize({"fixture":True})
    return ChatClient(ChatConfig(base_url="http://fixture/v1",model="fixture",max_context_tokens=100,max_output_tokens=20),
                      lambda *a:10,UsageBudget(budget),l,transport,finalization_reserve=8)

def response(content="{}",tokens=5,finish="stop"):
    return {"choices":[{"message":{"content":content},"finish_reason":finish}],"usage":{"prompt_tokens":10,"completion_tokens":tokens}}


def test_unknown_cost_is_charged_not_zero_and_resume_matches():
    calls=[]
    def transport(*a,**kw):
        calls.append(1)
        if len(calls)==1: raise HarnessError("service_error","HTTP 503")
        return response()
    c=client(transport); c.complete([{"role":"user","content":"x"}])
    assert c.budget.completion_tokens==5 and c.budget.charged_tokens==25 and c.budget.remaining==75
    b=UsageBudget(100,c.ledger.events()); assert b.summary()==c.budget.summary()


def test_unknown_response_usage_conservatively_reserves_request():
    c=client(lambda *a,**k:{"choices":[]})
    with pytest.raises(HarnessError): c.complete([{"role":"user","content":"x"}])
    assert c.budget.charged_tokens==20 and not c.budget.summary()["usage_complete"]


def test_crash_after_request_has_reserved_cost_on_resume():
    c=client(lambda *a,**k:response())
    c.ledger.append({"type":"generation_request","request_id":"unsettled","reserved_completion_tokens":20})
    b=UsageBudget(100,c.ledger.events()); assert b.charged_tokens==20 and b.unknown_usage_requests==1


def test_audit_reserve_leaves_policy_opportunity():
    c=client(lambda *a,**k:response(tokens=12),budget=20)
    c.complete([{"role":"user","content":"audit"}],purpose="audit")
    assert c.budget.remaining==8
    with pytest.raises(HarnessError) as e: c.complete([{"role":"user","content":"audit"}],purpose="audit")
    assert e.value.code=="audit_budget_reserved"


def test_missing_content_or_length_is_protocol_error_not_gap():
    for text,finish in [(None,"stop"),("{}","length")]:
        c=client(lambda *a,**k:response(text,finish=finish))
        with pytest.raises(HarnessError): c.complete([{"role":"user","content":"x"}])
        assert c.budget.completion_tokens==5


def test_no_credentials_persisted(monkeypatch):
    monkeypatch.setenv("ESR_API_KEY","DO_NOT_LOG_THIS_SECRET")
    def transport(*a,**kw):
        assert kw["headers"]["Authorization"].endswith("DO_NOT_LOG_THIS_SECRET")
        return response()
    c=client(transport); c.complete([{"role":"user","content":"x"}])
    assert "DO_NOT_LOG_THIS_SECRET" not in json.dumps(c.ledger.events())


def test_bad_quote_not_semantic_gap():
    h=env(); update(h,opened(h)); packet=h.audit_packet()
    report=h.auditor.audit(h.question,packet,list(h.observations.values()))
    report["claims"][0]["quotes"][0]["quote"]="invented content"
    with pytest.raises(HarnessError): validate_report(report,packet,h.observations)
    assert h.last_audit is None


def test_audit_repair_keeps_original_evidence_and_question():
    h=env(); update(h,opened(h)); good=h.auditor.audit(h.question,h.audit_packet(),list(h.observations.values()))
    class Fake:
        identity={"fixture":True}
        def __init__(self): self.requests=[]
        def complete(self,messages,purpose):
            self.requests.append(json.loads(json.dumps(messages)))
            return "bad JSON" if len(self.requests)==1 else json.dumps(good)
    c=Fake(); ModelAuditor(c).audit(h.question,h.audit_packet(),list(h.observations.values()))
    assert c.requests[1][:2]==c.requests[0]
    assert "Mira won the Lake Cup in 2010" in json.dumps(c.requests[1])


def test_invalid_policy_output_still_has_delivery_receipt():
    h=env(); o=opened(h,expose=False)
    class Invalid:
        def fits(self,messages): return True
        def complete(self,*a,**k): return "not json"
    h.config=type(h.config)(max_actions=3)  # isolate one remaining decision in this fixture
    result=run(h,Invalid())
    assert o in h.exposed and result["terminal"]["outcome"]=="budget_exhausted"


def test_new_smoke_is_a_scripted_complete_loop(tmp_path):
    path=tmp_path/"new.db"; r=smoke(str(path))
    assert r["attempts"]==11 and r["search_cache_hits"]==1 and r["exposed_observations"]==2
    h=replay(str(path)); assert h.terminal["answer"]=="Taylor"; h.ledger.close()


def test_root_replay_dispatches_frozen_v2_without_migration(tmp_path):
    from esr_harness.v2.demo import smoke as old_smoke
    path=tmp_path/"old.db"; old_smoke(str(path)); raw=path.read_bytes()
    h=replay(str(path)); assert h.ledger.header["schema_version"]==2
    h.ledger.close(); assert path.read_bytes()==raw
