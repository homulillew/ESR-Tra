"""Single native read-only request, audited without API calls."""
from copy import deepcopy
from dataclasses import replace
import pytest
from stride_search import Harness, Config, cli
from stride_search.archive import Archive
from stride_search.contract import digest, loads
from stride_search.fixtures import ScriptedModel, native, smoke_corpus
from stride_search.providers import AnthropicModel, HTTP
from stride_search.workflow_contract import WorkflowConfig
from test_middle_history import step, preview, READ, STOP
from test_relation_review import seed


def make(**kwargs):
    return Harness('Who directed Lumen?',smoke_corpus(),decision_protocol='read-only-once-v1',
                   config=kwargs.pop('config',Config(max_model_calls=12)),**kwargs)


def names(wire):return {t.get('function',t)['name'] for t in wire['tools']}


@pytest.mark.parametrize('full',[False,True])
def test_same_messages_only_read_then_restore(full):
    h=make(workflow=WorkflowConfig(enabled=full))
    try:
        seed(h);h.notes={'n':{'key':'n','text':'keep note','anchors':[],'order':1}}
        h.repair={'preview':'keep repair'}
        for g in h.groups:g['messages'][0]['reasoning_content']='keep reasoning'
        before=deepcopy(h.groups);seq=h.archive.seq
        p=preview(h);assert p==preview(h) and h.read_only.used==0 and h.archive.seq==seq
        assert names(p['wire'])=={'read'} and p['read_only_audit']['visible_read_documents']
        h.read_only=None;baseline=preview(h);from stride_search.decision_protocol import OnceProseState
        state=OnceProseState()
        for g in h.groups:state.complete(g)
        h.read_only=state
        assert p['wire']['messages']==baseline['wire']['messages']
        assert p['wire']['tools']==[t for t in baseline['wire']['tools'] if t['function']['name']=='read']
        wire=step(h,('read',{'ref':'d1','start':10,'length':80}))
        assert wire==p['wire'] and h.read_only.used==1 and h.groups[:-1]==before
        result=[e['payload'] for e in h.archive.events() if e['kind']=='action_result'][-1]
        assert loads(result['arguments'])=={'ref':'d1','start':10,'length':80}
        assert result['result']['evidence']['start']==10 and result['result']['evidence']['end']==90
        assert names(preview(h)['wire'])!={'read'}
    finally:h.close()


@pytest.mark.parametrize('count,remaining,final',[(2,9,False),(3,2,False),(3,9,True)])
def test_no_trigger_boundaries(count,remaining,final):
    h=make()
    try:
        seed(h)
        state=h.read_only.project(h.groups[:count],[],count,remaining=remaining,final=final)
        assert state['trigger'] is None
    finally:h.close()


def test_remaining_three_and_pending_raw():
    h=make(config=Config(max_model_calls=6))
    try:
        seed(h);assert names(preview(h)['wire'])=={'read'}
        h._snapshot('d1');e=h.archive.window('d1',0,10)
        group=deepcopy(h.groups[-1]);group['evidence']=[e['ref']]
        assert preview(h,groups=[*h.groups[:-1],group])['read_only_state']['trigger'] is None
    finally:h.close()


@pytest.mark.parametrize('full',[False,True])
def test_capacity_navigation_disappears_without_consumption(full):
    h=make(workflow=WorkflowConfig(enabled=full))
    try:
        seed(h)
        # Completed observations survive; retained history can contain no navigation.
        h.groups=[];h.workflow.gap=None
        before=deepcopy(h.__dict__['read_only'].__dict__);seq=h.archive.seq
        def counter(wire):
            scope=loads(wire['messages'][-1]['content'].split('\n',1)[1])
            pages=scope.get('recent_document_index_not_evidence',scope.get('research_workflow',{}).get('available_pages_not_ranked_for_relevance',[]))
            return h.config.context_limit if pages else 1
        if full:
            from stride_search.contract import ContractError
            # Existing full workflow retains navigation in control independently.
            with pytest.raises(ContractError,match='cannot fit'):preview(h,counter=counter)
            assert h.read_only.__dict__==before and h.archive.seq==seq
            h.navigation_history=[]
        p=preview(h,counter=counter)
        assert p['read_only_state']['trigger'] is None and names(p['wire'])!={'read'}
        assert h.read_only.__dict__==before and h.archive.seq==seq
    finally:h.close()


def test_compaction_preserves_trigger_and_actual_capacity():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups)
        def counter(w):return h.config.context_limit if sum(m['role']=='assistant' for m in w['messages'])>1 else 1
        p=preview(h,counter=counter)
        assert p['compacted'] and len(p['groups'])==1 and names(p['wire'])=={'read'}
        assert p['read_only_state']['trigger']['source_rounds']==[1,2,3] and h.groups==before
        normal=preview(h);h.config=replace(h.config,context_limit=normal['capacity']+h.config.response_reserve)
        assert preview(h)['wire']==normal['wire']
    finally:h.close()


@pytest.mark.parametrize('action',[STOP,('search',{'queries':['new']}),('find',{'ref':'d1','text':'Ada'})])
def test_nonread_rejected_once(action):
    h=make()
    try:
        seed(h);slots=h.action_slots;step(h,action)
        r=[e['payload'] for e in h.archive.events() if e['kind']=='action_result'][-1]
        assert r['result']['code']=='read_only_tool_only' and not r['executed'] and h.action_slots==slots
        assert h.read_only.used==1 and names(preview(h)['wire'])!={'read'}
    finally:h.close()


def test_failed_send_consumed_before_send():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups)
        class Fail(ScriptedModel):
            def send(self,wire):
                assert h.read_only.used==1 and list(h.archive.events())[-1]['kind']=='read_only_once'
                raise TimeoutError('fixture')
        h._step(Fail([]))
        assert h.model_calls==4 and h.groups==before and h.terminal['outcome']=='model_transport'
    finally:h.close()


def test_native_batch_and_anthropic_reasoning_preserved():
    h=make()
    try:
        seed(h)
        for g in h.groups:g['messages'][0]['_anthropic_blocks']=[{'type':'thinking','thinking':'keep','signature':'signature'}]
        before=deepcopy(h.groups)
        model=AnthropicModel('http://fixture.invalid','fixture',revision='fixture',http=HTTP())
        w=preview(h,model=model)['wire']
        assert names(w)=={'read'} and 'signature' in str(w) and h.groups==before
        script=ScriptedModel([native(('read',{'ref':'d1','start':0,'length':10}),('read',{'ref':'d1','start':10,'length':10}))])
        h._step(script)
        results=[e['payload'] for e in h.archive.events() if e['kind']=='action_result'][-2:]
        assert all(r['result']['ok'] for r in results) and len(h.groups[-1]['evidence'])==2
    finally:h.close()


def test_cli_full_sqlite(tmp_path,monkeypatch):
    question=tmp_path/'q.txt';question.write_text('Who directed Lumen?',encoding='utf8');db=tmp_path/'read.sqlite'
    replies=[native(('search',{'queries':[q]})) for q in ['Lumen','director','Observatory']]
    replies += [native(READ),native(('finish',{'answer':'Ada Rowan','refs':['e1']}))]
    model=ScriptedModel(replies);monkeypatch.setattr(cli,'_model',lambda args,http:model)
    monkeypatch.setattr(cli,'_retriever',lambda args,http:smoke_corpus())
    flags=['run','--allow-network','--accept-counter-estimate','--base-url','http://fixture.invalid','--model','fixture',
           '--model-revision','fixture','--retrieval-url','http://fixture.invalid','--index-id','fixture','--counter','utf8_bytes',
           '--question-file',str(question),'--db',str(db),'--max-model-calls','8','--context-limit','96000','--response-reserve','4096',
           '--workflow-profile','full','--decision-protocol','read-only-once-v1']
    result=cli.execute(cli.parser().parse_args(flags))
    assert result['terminal']['outcome']=='submitted' and len(model.requests)==5
    assert names(model.requests[3])=={'read'} and names(model.requests[4])!={'read'}
    a=Archive(db,readonly=True)
    try:
        events=list(a.events());trigger=[e['payload'] for e in events if e['kind']=='read_only_once']
        assert len(trigger)==1 and trigger[0]['wire_sha256']==digest(model.requests[3])
        request=next(e['payload'] for e in events if e['kind']=='model_request' and e['payload']['round']==4)
        assert a.load_request(request['request'])==model.requests[3]
        assert a.evidence('e1')['text'] and a.verify()
    finally:a.db.close()


def test_baseline_bytes_before_trigger():
    hs=[make(),Harness('Who directed Lumen?',smoke_corpus(),config=Config(max_model_calls=12))]
    try:
        for q in ['Lumen','director','Observatory']:
            assert preview(hs[0])['wire']==preview(hs[1])['wire']
            for h in hs:step(h,('search',{'queries':[q]}))
    finally:
        for h in hs:h.close()


def test_full_blocked_duplicate_not_successful():
    h=make(workflow=replace(WorkflowConfig.profile('full'),repeat_threshold=1))
    try:
        for _ in range(3):step(h,('search',{'queries':['Lumen']}))
        results=[e['payload'] for e in h.archive.events() if e['kind']=='action_result']
        assert any(r['result'].get('code')=='duplicate_query_blocked' for r in results)
        assert h.read_only.used==0 and preview(h)['read_only_state']['trigger'] is None
    finally:h.close()


def test_text_only_does_not_autoread_or_retry():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups);slots=h.action_slots
        h._step(ScriptedModel([native(content='I intend to read.')]))
        assert h.read_only.used==1 and h.model_calls==4 and h.groups==before and h.action_slots==slots
        assert names(preview(h)['wire'])!={'read'}
    finally:h.close()


def test_unknown_doc_remains_unauthorized():
    h=make()
    try:
        seed(h);step(h,('read',{'ref':'d999'}))
        r=[e['payload'] for e in h.archive.events() if e['kind']=='action_result'][-1]
        assert not r['result']['ok'] and not h.groups[-1]['evidence']
        assert h.read_only.used==1 and 'd999' not in h.published_docs
    finally:h.close()
