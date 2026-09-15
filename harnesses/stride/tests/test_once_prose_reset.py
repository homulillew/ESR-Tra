from copy import deepcopy
import pytest
from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.contract import digest
from stride_search.fixtures import ScriptedModel, smoke_corpus
from stride_search.providers import AnthropicModel, HTTP
from test_middle_history import step, preview, assistants, SEARCH, READ, STOP


def make(**kwargs):
    return Harness('Who directed Lumen?', smoke_corpus(), decision_protocol='once-prose-reset-v1',
                   config=kwargs.pop('config', Config(max_model_calls=9)), **kwargs)


def seed(h, count=3):
    for i in range(count):
        step(h, text=f'original {i}')


@pytest.mark.parametrize('count,final,expected', [(2,False,False),(3,False,True),(3,True,False)])
def test_trigger(count, final, expected):
    h=make()
    try:
        seed(h,count)
        p=preview(h,final=final)
        assert bool(p['once_prose_state']['trigger']) == expected
        assert p['capacity'] == h.counter(p['wire'])
    finally: h.close()


def test_read_and_last_two_do_not_trigger():
    for read in [True,False]:
        h=make(config=Config(max_model_calls=5 if not read else 9))
        try:
            seed(h,2)
            step(h, READ if read else SEARCH)
            assert preview(h)['once_prose_state']['trigger'] is None
        finally: h.close()


def test_one_request_then_restore_and_original_archive(tmp_path):
    path=tmp_path/'once.sqlite';h=make(path=path)
    try:
        seed(h)
        before=deepcopy(h.groups);seq=h.archive.seq
        a,b=preview(h),preview(h)
        assert a==b and h.groups==before and h.archive.seq==seq and h.once_prose.used==0
        expected=deepcopy(a['wire'])
        assert [m['content'] for m in assistants(expected)] == [None]*3
        for g,m in zip(before,assistants(expected)):
            original=deepcopy(g['messages'][0]);original['content']=None
            assert m==original
        wire=step(h,text='new response')
        assert wire==expected and h.once_prose.used==1
        assert h.groups[:3]==before
        restored=step(h,text='next response')
        assert [m['content'] for m in assistants(restored)][:3]==['original 0','original 1','original 2']
        step(h,STOP)
    finally:h.close()
    archive=Archive(path,readonly=True)
    try:
        events=list(archive.events()); audits=[e['payload'] for e in events if e['kind']=='once_prose_reset']
        assert len(audits)==1 and audits[0]['source_rounds']==[1,2,3]
        assert audits[0]['wire_sha256']==digest(wire)
        assert 'episode_first_complete_round' not in audits[0]
        assert 'latest_complete_round' not in audits[0]
        assert 'first_complete_group_present' not in audits[0]
        assert [c['source_round'] for c in audits[0]['changes']]==[1,2,3]
        groups=[archive.json(e['payload']['group']) for e in events if e['kind']=='round_end']
        assert groups[:3]==before
        archive.verify()
    finally:archive.db.close()


def test_eviction_keeps_observations_and_preserves_notes_repair():
    h=make()
    try:
        seed(h);h.groups=h.groups[-1:]
        h.repair={'preview':'old speculation'}
        original=deepcopy(h.groups)
        p=preview(h)
        assert p['once_prose_state']['trigger']['source_rounds']==[1,2,3]
        assert len(assistants(p['wire']))==1 and assistants(p['wire'])[0]['content'] is None
        assert h.groups==original and h.once_prose.used==0
        assert 'old speculation' in str(p['wire'])
    finally:h.close()


def test_native_wire_preserves_signed_blocks_and_receipts():
    h=make(); model=AnthropicModel('http://fixture.invalid','fixture',revision='fixture',http=HTTP())
    try:
        seed(h)
        for g in h.groups:
            raw={'role':'assistant','stop_reason':'tool_use','content':[
                {'type':'text','text':'speculation'},
                {'type':'thinking','thinking':'reason','signature':'signed'},
                {'type':'tool_use','id':'call_0','name':'search','input':SEARCH[1]}]}
            g['messages'][0]=model.parse(raw).message
        before=deepcopy(h.groups);p=preview(h,model=model)
        for m in assistants(p['wire']):
            assert [b['type'] for b in m['content']]==['thinking','tool_use']
            assert m['content'][0]['signature']=='signed'
        receipts=[b for m in p['wire']['messages'] for b in m['content'] if b['type']=='tool_result']
        assert [b['content'] for b in receipts]==[g['messages'][1]['content'] for g in before]
        assert h.groups==before
    finally:h.close()


def test_formal_cli():
    flags=['run','--base-url','http://fixture.invalid','--model','fixture','--model-revision','fixture',
           '--retrieval-url','http://fixture.invalid','--index-id','fixture','--counter','utf8_bytes',
           '--question-file','fixture','--db','fixture.sqlite','--decision-protocol','once-prose-reset-v1']
    flags += ['--max-model-calls','8','--context-limit','96000','--response-reserve','4096']
    assert cli.parser().parse_args(flags).decision_protocol=='once-prose-reset-v1'


def test_pending_source_preflight_does_not_consume_or_mutate():
    h=make()
    try:
        seed(h)
        before=deepcopy(h.once_prose.__dict__)
        projection=h.once_prose.project(h.groups, ['e999'], h.model_calls, remaining=6, final=False)
        assert projection['trigger'] is None
        assert h.once_prose.__dict__==before
        assert preview(h)['once_prose_state']['trigger'] is not None
    finally:h.close()


def test_nonexecuted_search_breaks_streak():
    h=make()
    try:
        seed(h,2)
        step(h, ('search', {'queries': []}))
        assert preview(h)['once_prose_state']['trigger'] is None
    finally:h.close()


def test_commit_and_audit_precede_only_send():
    from stride_search.fixtures import native
    h=make()
    try:
        seed(h)
        class CheckingModel(ScriptedModel):
            def send(self, wire):
                assert h.once_prose.used==1
                kinds=[e['kind'] for e in h.archive.events()]
                assert kinds[-2:]==['model_request','once_prose_reset']
                return super().send(wire)
        model=CheckingModel([native(STOP)])
        h._step(model)
        assert len(model.requests)==1 and h.model_calls==4
    finally:h.close()

def test_projection_changes_only_prose_with_existing_source_and_notes():
    h=make(config=Config(max_model_calls=12))
    try:
        step(h);step(h,READ)
        seed(h,3)
        h.notes={'n': {'key':'n','text':'candidate guess','anchors':[], 'order':1}}
        h.repair={'preview':'uncommitted guess'}
        projected=preview(h)
        state=h.once_prose;h.once_prose=None;h.decision_protocol='baseline'
        baseline=preview(h)
        h.once_prose=state;h.decision_protocol='once-prose-reset-v1'
        expected=deepcopy(baseline['wire'])
        for m in assistants(expected):m['content']=None
        assert projected['wire']==expected
        assert projected['visible']==baseline['visible'] and projected['visible']
        assert projected['groups']==baseline['groups']
    finally:h.close()

def test_formal_cli_full_execution_and_sqlite(tmp_path, monkeypatch):
    from stride_search.fixtures import native
    question=tmp_path/'question.txt';question.write_text('Who directed Lumen?',encoding='utf-8')
    database=tmp_path/'cli.sqlite'
    model=ScriptedModel([
        native(('search',{'queries':['Lumen']}),content='first guess'),
        native(('search',{'queries':['director']}),content='second guess'),
        native(('search',{'queries':['Observatory']}),content='third guess'),
        native(READ,content='read source'),
        native(('finish',{'answer':'Ada Rowan','refs':['e1']}))])
    monkeypatch.setattr(cli,'_model',lambda args,http:model)
    monkeypatch.setattr(cli,'_retriever',lambda args,http:smoke_corpus())
    flags=['run','--allow-network','--accept-counter-estimate','--base-url','http://fixture.invalid',
           '--model','fixture','--model-revision','fixture','--retrieval-url','http://fixture.invalid',
           '--index-id','fixture','--counter','utf8_bytes','--question-file',str(question),'--db',str(database),
           '--max-model-calls','8','--context-limit','96000','--response-reserve','4096',
           '--workflow-profile','full','--decision-protocol','once-prose-reset-v1']
    result=cli.execute(cli.parser().parse_args(flags))
    assert result['terminal']['outcome']=='submitted'
    assert result['terminal']['answer']=='Ada Rowan' and len(model.requests)==5
    assert [m['content'] for m in assistants(model.requests[3])]==[None]*3
    assert [m['content'] for m in assistants(model.requests[4])][:3]==['first guess','second guess','third guess']
    a=Archive(database,readonly=True)
    try:
        events=list(a.events());audits=[e['payload'] for e in events if e['kind']=='once_prose_reset']
        assert len(audits)==1 and audits[0]['round']==4
        assert audits[0]['identity']['version']=='once-prose-reset-v1'
        requests=[e['payload'] for e in events if e['kind']=='model_request']
        assert a.load_request(requests[3]['request'])==model.requests[3]
        groups=[a.json(e['payload']['group']) for e in events if e['kind']=='round_end']
        assert groups[0]['messages'][0]['content']=='first guess'
        a.verify()
    finally:a.db.close()

def test_capacity_rebuild_preserves_trigger_and_original_groups():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups);seq=h.archive.seq
        def counter(wire):
            return h.config.context_limit if len(assistants(wire))>1 else 1
        a=preview(h,counter=counter,groups=h.groups)
        b=preview(h,counter=counter,groups=h.groups)
        assert a==b and a['compacted'] and len(a['groups'])==1
        assert a['once_prose_state']['trigger']['source_rounds']==[1,2,3]
        assert [m['content'] for m in assistants(a['wire'])]==[None]
        assert a['groups'][0]==before[-1]
        assert h.groups==before and h.archive.seq==seq and h.once_prose.used==0
    finally:h.close()


def test_failed_send_consumes_one_attempt_without_mutating_groups():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups)
        class Failing(ScriptedModel):
            def send(self,wire):raise TimeoutError('synthetic')
        h._step(Failing([]))
        events=list(h.archive.events())
        assert h.model_calls==4 and h.once_prose.used==1 and h.groups==before
        assert len([e for e in events if e['kind']=='once_prose_reset'])==1
        assert len([e for e in events if e['kind']=='model_request'])==4
        assert h.terminal['outcome']=='model_transport'
    finally:h.close()


def test_full_workflow_blocked_duplicate_is_not_successful_search():
    from stride_search.workflow_contract import WorkflowConfig
    from dataclasses import replace
    h=make(workflow=replace(WorkflowConfig.profile('full'), repeat_threshold=1))
    try:
        seed(h)
        results=[e['payload'] for e in h.archive.events() if e['kind']=='action_result']
        assert any(r['result'].get('code')=='duplicate_query_blocked' for r in results)
        assert preview(h)['once_prose_state']['trigger'] is None
        assert h.once_prose.used==0
    finally:h.close()
