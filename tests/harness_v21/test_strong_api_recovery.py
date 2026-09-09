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


@pytest.mark.parametrize("fields",[{"attempt_note":42},{"attempt_note":"note","attempt_id":[]},{"attempt_id":False}])
def test_malformed_auxiliary_fields_do_not_erase_valid_research(fields):
    h=env();r=update(h,opened(h),**fields)
    assert r["ok"] and r["warnings"] and h.state["answer"]=="Taylor"
    assert "attempt_note" not in h.actions[-1]["delta"]


def test_semantic_error_retains_proposal_for_single_local_repair():
    h=env(); oid=opened(h)
    patch={"answer":"Taylor","claim_updates":[{"claim_id":"c0","finding":"relation","observation_ids":[oid]}],
           "focus":{"claim_id":"c99","need":"relation"}}
    before=deepcopy(h.state)
    assert not h.execute("update_state",patch)["ok"] and h.state == before
    assert h.context()["failed_proposal"]["arguments"] == patch
    patch["focus"]["claim_id"]="c0"
    assert h.execute("update_state",patch)["ok"] and h.state["answer"]=="Taylor"


def test_cite_dismiss_conflict_identifies_field_and_ids_for_one_repair():
    h=env();o=opened(h)
    patch={"answer":"Taylor","claim_updates":[{"claim_id":"c0","finding":"relation","observation_ids":[o]}],
           "dismiss_observation_ids":[o]}
    r=h.execute("update_state",patch)
    assert not r["ok"] and r["error_path"]=="arguments.dismiss_observation_ids" and o in r["error"]
    assert h.state["answer"] is None
    patch["dismiss_observation_ids"]=[]
    assert h.execute("update_state",patch)["ok"] and not h.pending


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


def test_native_tool_availability_retains_all_recovery_routes():
    h=env()
    tools={t['name']:t for t in h.available_tools()}
    assert 'verify_answer' not in tools and 'open_page' not in tools
    assert tools['submit_answer']['parameters']['properties']['decision']['enum']==['abstain']
    oid=opened(h)
    assert 'verify_answer' not in {t['name'] for t in h.available_tools()}
    assert update(h,oid,focus=None)['ok']
    tools={t['name']:t for t in h.available_tools()}
    assert 'verify_answer' in tools
    assert 'observation_id' not in tools['read_evidence']['parameters']['properties']
    assert 'update_state' in tools and 'search' in tools  # either can restore focus
    h.execute('update_state',{'focus':{'claim_id':'c0','need':'inspect source'}})
    assert 'observation_id' in next(t for t in h.available_tools() if t['name']=='read_evidence')['parameters']['properties']
    h.execute('verify_answer')
    assert 'verify_answer' not in {t['name'] for t in h.available_tools()}
    assert h.execute('verify_answer')['cached']  # cache remains available to direct/replay clients


@pytest.mark.parametrize('mode',['baseline','esr'])
def test_readable_id_enum_never_leaks_into_other_tool_fields(mode):
    from esr_harness.protocol import canonical,SCHEMAS,validate
    before=canonical(SCHEMAS)
    h=env(config=Config(mode=mode,audit_mode='off'));oid=opened(h)
    tools={t['name']:t['parameters'] for t in h.available_tools()}
    assert tools['read_evidence']['properties']['observation_id']['enum']==[oid]
    assert 'enum' not in tools['open_page']['properties']['docid']
    assert 'enum' not in tools['open_page']['properties']['search_action_id']
    validate({'docid':'d1'},tools['open_page'])
    if mode=='esr':
        validate({'query':'Lake','focus':{'claim_id':'c0','need':'inspect source'}},tools['search'])
        validate({'claim_updates':[{'claim_id':'c0','finding':'Source fact','observation_ids':[oid]}]},tools['update_state'])
        assert 'enum' not in tools['update_state']['properties']['attempt_id']
    assert canonical(SCHEMAS)==before


def test_baseline_retains_full_observations_and_query_results():
    h=env(config=Config(mode="baseline",audit_mode="off")); o=opened(h)
    h.execute("search",{"query":"Other"})
    messages=messages_for(h,SimpleNamespace(fits=lambda _:True))
    rendered=json.dumps(messages)
    returned = [json.loads(m["content"]) for m in messages if m["role"] == "user"]
    assert any(r.get("observation", {}).get("text") == h.observations[o]["text"] for r in returned)
    assert any('"results"' in m["content"] and 'd1' in m["content"] for m in messages)
    assert not any('"claim_updates"' in m["content"] for m in messages)


def test_baseline_never_renders_internal_raw_parts_or_repeats_identical_views():
    h=env(config=Config(mode="baseline",audit_mode="off"));o=opened(h)
    h.execute('read_evidence',{'observation_id':o})
    messages=messages_for(h,SimpleNamespace(fits=lambda _:True))
    results=[json.loads(m['content']) for m in messages if m['role']=='user']
    views=[r['observation'] for r in results if 'observation' in r]
    assert len([v for v in views if 'text' in v])==1
    assert views[0]['text']==h.observations[o]['text']
    assert views[1]['identical_body_at_action']=='a2'
    assert 'raw_parts' not in json.dumps(messages)


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


def test_daily_quota_holds_all_purposes_across_restart_without_refunding(tmp_path):
    import httpx
    from dataclasses import replace
    error=httpx.HTTPStatusError('quota',request=httpx.Request('POST','http://fixture'),
                               response=httpx.Response(429,text=json.dumps({'error':{'message':'超过EB模型每日最多调用次数'}})))
    c=client(tmp_path,[error,response()]);c.config=replace(c.config,transport_attempts=2)
    with pytest.raises(HarnessError,match='daily request quota'):c.complete([{'role':'user','content':'fixture'}])
    assert len(c.transport.requests)==1 and c.budget.charged_tokens==32
    assert c.global_budget.summary()['purposes'][0]['unknown_or_outstanding_requests']==1
    resumed=client(tmp_path,[response()])
    with pytest.raises(HarnessError,match='paused'):resumed.complete([{'role':'user','content':'fixture'}],purpose='judge')
    with pytest.raises(HarnessError):resumed.global_budget.episode('new','development')
    assert resumed.transport.requests==[] and resumed.budget.charged_tokens==0


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


def test_native_report_preserves_report_shape_and_exact_active_ids(tmp_path):
    from esr_harness.audit import ModelAuditor
    from esr_harness.protocol import canonical, AUDIT_SCHEMA
    h=env();update(h,opened(h))
    report=h.auditor.audit(h.question,h.state,list(h.observations.values()))
    r=response();r['stop_reason']='tool_use';r['content']=[{'type':'tool_use','name':'audit_report','id':'report','input':report}]
    c=client(tmp_path,[r]);c.budget=UsageBudget(2000)
    received=ModelAuditor(c).audit(h.question,h.state,list(h.observations.values()))
    assert received==report
    schema=c.transport.requests[0]['tools'][0]['input_schema']
    assert schema['properties']['claims']['minItems']==schema['properties']['claims']['maxItems']==1
    assert schema['properties']['claims']['items']['properties']['claim_id']['enum']==['c0']
    assert 'enum' not in AUDIT_SCHEMA['properties']['claims']['items']['properties']['claim_id']
    assert 'enum' not in schema['properties']['claims']['items']['properties']['quotes']['items']['properties']['observation_id']


def test_dispatcher_preserves_contract_and_rejects_multiple_proposals(tmp_path):
    from dataclasses import replace
    from esr_harness.protocol import canonical, validate
    cfg=Config(mode='baseline',audit_mode='off')
    messages=[{'role':'system','content':'Call one tool.\nTools:\n'+canonical(cfg.tools)},
              {'role':'user','content':'fixture'}]
    proposal={'action':'finish','arguments':{'answer':'fixture'}}
    r=response();r['stop_reason']='tool_use'
    r['content']=[{'type':'tool_use','id':'call1','name':'take_action','input':proposal}]
    bad={**r,'content':[dict(r['content'][0],input={'action':'finish','arguments':{'unexpected':1}})]}
    c=client(tmp_path,[r,{**r,'content':r['content']*2},bad])
    c.config=replace(c.config,policy_tool_interface='dispatcher')
    assert json.loads(c.complete(messages))==proposal
    body=c.transport.requests[0]
    assert len(body['tools'])==1 and body['tool_choice']['name']=='take_action'
    branches=body['tools'][0]['input_schema']['oneOf']
    assert {b['properties']['action']['enum'][0]:b['properties']['arguments'] for b in branches}=={t['name']:t['parameters'] for t in cfg.tools}
    with pytest.raises(HarnessError,match='exactly one'):c.complete(messages)
    parsed=json.loads(c.complete(messages))
    assert parsed['arguments']=={'unexpected':1}
    with pytest.raises(HarnessError):validate(parsed['arguments'],cfg.tool_schema('finish'),'arguments')


def test_undeclared_single_tool_is_not_misreported_as_parallel_calls(tmp_path):
    from esr_harness.protocol import canonical
    cfg=Config(mode='baseline',audit_mode='off')
    r=response();r['stop_reason']='tool_use'
    r['content']=[{'type':'tool_use','name':'missing_tool','input':{}}]
    c=client(tmp_path,[r])
    with pytest.raises(HarnessError,match='not available') as exc:
        c.complete([{'role':'system','content':'Tools:\nignored\nTools:\n'+canonical(cfg.tools)}])
    assert 'missing_tool' in str(exc.value) and 'parallel' not in str(exc.value)


def test_text_interface_preserves_full_contract_and_strict_action_envelope(tmp_path):
    from dataclasses import replace
    from esr_harness.protocol import canonical, parse_object
    cfg=Config(mode='baseline',audit_mode='off')
    messages=[{'role':'system','content':'One JSON action.\nTools:\n'+canonical(cfg.tools)},
              {'role':'user','content':'fixture'}]
    r=response();r['content'][0]['text']='{}{}'
    c=client(tmp_path,[response(),r]);c.config=replace(c.config,policy_tool_interface='text')
    assert parse_object(c.complete(messages))['action']=='finish'
    body=c.transport.requests[0]
    assert 'tools' not in body and 'tool_choice' not in body and body['system']==messages[0]['content']
    with pytest.raises(HarnessError):parse_object(c.complete(messages))
    audit_body=c.body([{'role':'system','content':'Audit.\nSchema:\n'+canonical({'type':'object'})}],32)
    assert audit_body['tools'][0]['name']=='audit_report'


def test_context_check_is_finite(tmp_path):
    c=client(tmp_path,[])
    assert not c.fits([{"role":"user","content":"X"*70000}])


def test_observed_gateway_end_token_is_only_removed_after_strict_whole_json_validation(tmp_path):
    from esr_harness.remote import normalize_tool_text
    raw='{"action":"search","arguments":{"query":"synthetic"}}</tool_call>'
    normalized,rule=normalize_tool_text(raw)
    assert json.loads(normalized)=={'action':'search','arguments':{'query':'synthetic'}}
    assert rule=='json_object_tool_end_suffix_v1'
    for malformed in ['{"action":"finish"}}', '{}{}', '{"x":1,"x":2}', '{"x":NaN}']:
        with pytest.raises(HarnessError):normalize_tool_text(malformed+'</tool_call>')
    prose='Example: '+raw
    assert normalize_tool_text(prose)==(prose,None)
    r=response();r['content']=[{'type':'text','text':raw}]
    c=client(tmp_path,[r]);assert json.loads(c.complete([{'role':'user','content':'fixture'}]))['action']=='search'
    event=c.ledger.events()[-1]
    assert event['type']=='response_normalization' and event['semantic_fields_modified'] is False


def test_search_capacity_failure_keeps_next_request_executable_and_allows_smaller_retry():
    from esr_harness.protocol import canonical
    class LargeHits(MemoryRetriever):
        def __init__(self):
            super().__init__([]);self.calls=[]
        def search(self,query,top_k):
            self.calls.append(top_k)
            return [{'docid':str(i),'title':'fixture','snippet':'evidence '*100,'score':1.0} for i in range(top_k)]
    class Policy:
        limit=100000
        def __init__(self):self.requests=[]
        def fits(self,messages):return len(canonical(messages))<=self.limit
        def complete(self,messages,purpose):
            self.requests.append(messages)
            return canonical([{'action':'search','arguments':{'query':'fixture','top_k':20}},
                              {'action':'search','arguments':{'query':'fixture','top_k':1}},
                              {'action':'finish','arguments':{'answer':'synthetic'}}][len(self.requests)-1])
    retriever=LargeHits();h=Harness('Synthetic capacity test',retriever,config=Config(mode='baseline'))
    c=Policy();c.limit=len(canonical(messages_for(h,c)))+4500
    result=run(h,c)
    assert result['terminal']['outcome']=='submitted'
    assert retriever.calls==[20,1] and set(h.searches)=={'a2'}
    assert h.actions[0]['result']['error_code']=='context_capacity'
    assert 'no hits were admitted' in canonical(c.requests[1])
    assert all(c.fits(m) for m in c.requests)


def test_remote_admission_reserves_error_recovery_space(tmp_path):
    c=client(tmp_path,[])
    messages=[{'role':'user','content':'synthetic'}]
    from dataclasses import replace
    maximum=min(c.config.max_output_tokens,c.budget.remaining)
    need=c.input_reservation(c.body(messages,maximum))+maximum
    c.config=replace(c.config,context_operating_cap=need+1000)
    assert c.fits(messages) and not c.fits_for_admission(messages)
    assert c.context_status(messages)['remaining_units_before_this_status']==1000


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
