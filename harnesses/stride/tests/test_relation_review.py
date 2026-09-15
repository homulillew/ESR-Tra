"""Offline actual-wire and CLI checks for the temporary relation-review request."""
from copy import deepcopy
import pytest
from stride_search import Config, Harness, cli
from stride_search.archive import Archive
from stride_search.contract import loads, digest
from stride_search.fixtures import ScriptedModel, smoke_corpus, native
from stride_search.relation_review import INSTRUCTION
from stride_search.workflow_contract import WorkflowConfig
from test_middle_history import step, preview, SEARCH, READ, STOP


def make(**kwargs):
    return Harness('Who directed Lumen?', smoke_corpus(), decision_protocol='relation-review-once-v1',
                   config=kwargs.pop('config',Config(max_model_calls=12)), **kwargs)


def seed(h):
    for q in ['Lumen','director','Observatory']:
        step(h,('search',{'queries':[q]}),text='OLD_GUESS')


def packet(wire):
    return loads(wire['messages'][2]['content'].split('\n',1)[1])


@pytest.mark.parametrize('raw',[False,True])
def test_one_review_raw_scope_original_history_and_restore(raw):
    h=make()
    try:
        if raw:step(h);step(h,READ)
        seed(h)
        h.notes={'n':{'key':'n','text':'NOTE_GUESS','anchors':[],'order':1}}
        h.repair={'preview':'REPAIR_GUESS'}
        for g in h.groups:g['messages'][0]['reasoning_content']='PROVIDER_GUESS'
        before=deepcopy(h.groups);seq=h.archive.seq
        p=preview(h);again=preview(h)
        assert p==again and h.archive.seq==seq and h.relation_review.used==0
        assert p['groups']==before and p['capacity']==h.counter(p['wire'])
        assert INSTRUCTION in p['wire']['messages'][0]['content']
        assert all(m['role'] in ('system','user') for m in p['wire']['messages'])
        assert not any(x in str(p['wire']) for x in ['OLD_GUESS','NOTE_GUESS','REPAIR_GUESS','PROVIDER_GUESS'])
        data=packet(p['wire'])
        assert bool(data['raw_source_windows_untrusted'])==raw
        assert {w['ref'] for w in data['raw_source_windows_untrusted']}==set(p['visible'])
        for g,row in zip(before,data['untrusted_execution_records_not_evidence']):
            c=g['messages'][0]['tool_calls'][0]
            assert row['source_group_sha256']==digest(g)
            assert row['calls'][0]['id']==c['id']
            assert row['calls'][0]['raw_arguments']==c['function']['arguments']
            assert row['calls'][0]['receipt']==g['messages'][1]
        assert {t['function']['name'] for t in p['wire']['tools']}=={'search','read','find'}
        actual=step(h,READ,text='REVIEW_PROSE')
        assert actual==p['wire'] and h.relation_review.used==1
        assert h.groups[:len(before)]==before
        after=preview(h)['wire']
        assert INSTRUCTION not in after['messages'][0]['content']
        assert 'OLD_GUESS' in str(after) and 'REVIEW_PROSE' in str(after)
    finally:h.close()


@pytest.mark.parametrize('final,remaining',[(True,8),(False,3)])
def test_no_trigger_final_or_low_budget(final,remaining):
    h=make()
    try:
        seed(h)
        state=h.relation_review.project(h.groups,[],h.model_calls,remaining=remaining,final=final)
        assert state['trigger'] is None
    finally:h.close()


def test_capacity_rebuild_and_unseen_raw_scope():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups);seq=h.archive.seq
        def counter(wire):
            n=len(packet(wire)['untrusted_execution_records_not_evidence'])
            return h.config.context_limit if n>1 else 1
        a=preview(h,counter=counter);b=preview(h,counter=counter)
        assert a==b and a['compacted'] and len(a['groups'])==1
        assert a['relation_review_state']['trigger']['source_rounds']==[1,2,3]
        assert h.groups==before and h.archive.seq==seq and h.relation_review.used==0
        h._snapshot('d1'); hidden=h.archive.window('d1',0,10)
        assert hidden['ref'] not in preview(h)['visible']
        assert packet(preview(h)['wire'])['raw_source_windows_untrusted']==[]
    finally:h.close()


def test_restricted_native_call_is_explicit_error_then_normal_recovers():
    h=make()
    try:
        seed(h);before=h.action_slots
        step(h,STOP,text='review')
        result=[e['payload'] for e in h.archive.events() if e['kind']=='action_result'][-1]
        assert result['tool']=='finish' and result['result']['code']=='relation_review_tool_only'
        assert not result['executed'] and h.action_slots==before and h.terminal is None
        step(h,STOP)
        assert h.terminal['outcome']=='abstained' and h.model_calls==5
    finally:h.close()


def test_failed_send_archived_and_consumed_once():
    h=make()
    try:
        seed(h);before=deepcopy(h.groups)
        class Failure(ScriptedModel):
            def send(self,wire):
                assert h.relation_review.used==1
                assert list(h.archive.events())[-1]['kind']=='relation_review'
                raise TimeoutError('fixture')
        h._step(Failure([]))
        assert h.groups==before and h.model_calls==4 and h.terminal['outcome']=='model_transport'
        assert len([e for e in h.archive.events() if e['kind']=='relation_review'])==1
    finally:h.close()


def test_cli_full_workflow_native_response_sqlite(tmp_path,monkeypatch):
    question=tmp_path/'q.txt';question.write_text('Who directed Lumen?',encoding='utf-8')
    db=tmp_path/'review.sqlite'
    replies=[native(('search',{'queries':[q]}),content='OLD_GUESS') for q in ['Lumen','director','Observatory']]
    replies += [native(READ,content='UNVERIFIED_REVIEW'),native(('finish',{'answer':'Ada Rowan','refs':['e1']}))]
    model=ScriptedModel(replies)
    monkeypatch.setattr(cli,'_model',lambda args,http:model)
    monkeypatch.setattr(cli,'_retriever',lambda args,http:smoke_corpus())
    args=['run','--allow-network','--accept-counter-estimate','--base-url','http://fixture.invalid',
          '--model','fixture','--model-revision','fixture','--retrieval-url','http://fixture.invalid',
          '--index-id','fixture','--counter','utf8_bytes','--question-file',str(question),'--db',str(db),
          '--max-model-calls','8','--context-limit','96000','--response-reserve','4096',
          '--workflow-profile','full','--decision-protocol','relation-review-once-v1']
    report=cli.execute(cli.parser().parse_args(args))
    assert report['terminal']['outcome']=='submitted' and len(model.requests)==5
    a=Archive(db,readonly=True)
    try:
        events=list(a.events());audit=[e['payload'] for e in events if e['kind']=='relation_review']
        assert len(audit)==1 and audit[0]['round']==4 and audit[0]['wire_sha256']==digest(model.requests[3])
        groups=[a.json(e['payload']['group']) for e in events if e['kind']=='round_end']
        assert groups[3]['messages'][0]['content']=='UNVERIFIED_REVIEW'
        call=groups[3]['messages'][0]['tool_calls'][0]
        assert call['function']['name']=='read'
        assert groups[3]['messages'][1]['tool_call_id']==call['id']
        assert groups[0]['messages'][0]['content']=='OLD_GUESS'
        assert 'OLD_GUESS' in str(model.requests[4])
        a.verify()
    finally:a.db.close()

def test_nonretrieval_state_is_hashed_not_exposed_and_navigation_retained():
    from stride_search.relation_review import render
    group={'round':1,'messages':[
        {'role':'assistant','content':'OLD','tool_calls':[{'id':'n','function':{'name':'note','arguments':'NOTE_SECRET'}}]},
        {'role':'tool','tool_call_id':'n','content':'NOTE_SECRET'}]}
    before=deepcopy(group)
    scope={'remaining':{'model_calls':5},'phase':'RESEARCH','current_notes_not_evidence':['NOTE_SECRET'],
           'uncommitted_response_not_evidence':'REPAIR_SECRET','research_workflow':{
           'active_gap_not_verified':'GAP_SECRET','previous_gap_judgments_not_verified':['GAP_SECRET'],
           'stage':'normal','available_pages_not_ranked_for_relevance':[{'ref':'d1'}]}}
    messages,tools,audit=render('policy','question',[group],[],scope,[])
    assert not any(s in str(messages) for s in ['NOTE_SECRET','REPAIR_SECRET','GAP_SECRET'])
    data=loads(messages[2]['content'].split('\n',1)[1])
    row=data['untrusted_execution_records_not_evidence'][0]['calls'][0]
    assert row['id']=='n' and row['name']=='note' and row['body_omitted']
    assert row['source_call_sha256']==digest(group['messages'][0]['tool_calls'][0])
    assert data['control']['research_workflow']['available_pages_not_ranked_for_relevance']==[{'ref':'d1'}]
    assert group==before and scope['current_notes_not_evidence']==['NOTE_SECRET']


def test_baseline_wire_before_trigger_and_pending_raw_cancels_review():
    hs=[make(),Harness('Who directed Lumen?',smoke_corpus(),config=Config(max_model_calls=12))]
    try:
        for i in range(3):
            assert preview(hs[0])['wire']==preview(hs[1])['wire']
            for h in hs:step(h,('search',{'queries':[['Lumen','director','Observatory'][i]]}))
        h=hs[0];before=deepcopy(h.relation_review.__dict__)
        state=h.relation_review.project(h.groups,['e999'],h.model_calls,remaining=9,final=False)
        assert state['trigger'] is None and h.relation_review.__dict__==before
    finally:
        for h in hs:h.close()


def test_review_anthropic_wire_has_no_old_native_reasoning():
    from stride_search.providers import AnthropicModel, HTTP
    h=make();model=AnthropicModel('http://fixture.invalid','fixture',revision='fixture',http=HTTP())
    try:
        seed(h)
        for g in h.groups:
            g['messages'][0]['_anthropic_blocks']=[{'type':'thinking','thinking':'OLD_THINKING','signature':'OLD_SIGNATURE'}]
        before=deepcopy(h.groups);wire=preview(h,model=model)['wire']
        assert 'OLD_THINKING' not in str(wire) and 'OLD_SIGNATURE' not in str(wire)
        assert all(m['role']=='user' for m in wire['messages'])
        assert {t['name'] for t in wire['tools']}=={'search','read','find'}
        assert h.groups==before
    finally:h.close()
